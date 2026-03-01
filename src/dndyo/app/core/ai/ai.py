import json
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast

from mistralai import Mistral
from sqlmodel import Session, col, select

from dndyo.app.core.config import get_settings
from dndyo.app.core.db import engine
from dndyo.app.core.ai.tools import state as state_tools
from dndyo.app.models.actor import Actor
from dndyo.app.models.game import Game
from dndyo.app.models.game_state import GameState
from dndyo.app.models.live_actor import LiveActor, LiveActorRole
from dndyo.app.models.map import Map

TOOLS = state_tools.TOOLS
SYSTEM_PROMPT = (
    "You are the Dungeon Master of a Dungeons & Dragons game. "
    "Lead the game, narrate scenes, control pacing, and guide players through "
    "decisions and outcomes. Don't take decisions or actions for them. "
    "Be coincise but creative, answer in human tone, make the atmosphere interesting,"
    "if asked say, but don't say too much. "
    "You can access tools to inspect and update game state; use those tools when "
    "needed to keep the game state accurate."
    "Answer directly, you are the narrator voice, you don't need introductions"
)
SYSTEM_CONTEXT_PROMPT_PREFIX = "Game context for this run:"


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {}


def _build_game_context_system_message(game_id: int) -> str:
    with Session(engine) as session:
        game = session.exec(select(Game).where(Game.id == game_id)).first()
        state = session.exec(select(GameState).where(GameState.id == game_id)).first()

        first_chapter = "Unknown"
        if game is not None and game.chapters:
            first_chapter = game.chapters[0]

        player_rows = session.exec(
            select(LiveActor, Actor)
            .join(Actor, Actor.id == LiveActor.actor_id)
            .where(
                col(LiveActor.game_id) == game_id,
                col(Actor.game_id) == game_id,
                col(LiveActor.role) == LiveActorRole.player,
            )
            .order_by(col(LiveActor.id))
        ).all()
        players = [
            {
                "name": actor.name,
                "background": live_actor.background,
            }
            for live_actor, actor in player_rows
        ]

        state_payload = state_tools.get_game_state({}, game_id=game_id)
        current_map = state_payload.get("current_map") or {}
        connected_map_ids = current_map.get("connected_maps_ids") or []
        connected_maps = []
        for map_id in connected_map_ids:
            db_connected_map = session.exec(
                select(Map).where(
                    Map.id == map_id,
                    Map.game_id == game_id,
                )
            ).first()
            if db_connected_map is None:
                connected_maps.append({"id": map_id, "name": "Unknown"})
            else:
                connected_maps.append(
                    {
                        "id": db_connected_map.id,
                        "name": db_connected_map.name,
                    }
                )
        game_state = {
            "current_map_id": state_payload.get("current_map_id"),
            "current_map": {
                "id": current_map.get("id"),
                "name": current_map.get("name"),
                "connected_maps": connected_maps,
            },
            "environment_description": state_payload.get(
                "environment_description",
                state.environment_description if state is not None else "",
            ),
            "live_actors": state_payload.get("live_actors", []),
        }

    context_payload = {
        "first_chapter": first_chapter,
        "players": players,
        "game_state": game_state,
    }
    return (
        f"{SYSTEM_CONTEXT_PROMPT_PREFIX}\n"
        f"{json.dumps(context_payload, ensure_ascii=True)}"
    )


def _build_client() -> Mistral:
    settings = get_settings()
    kwargs: dict[str, Any] = {"api_key": settings.mistral_api_key}
    if settings.mistral_server_url:
        kwargs["server_url"] = settings.mistral_server_url
    return Mistral(**kwargs)


def _chat_create(
    client: Mistral,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    stream: bool = False,
) -> Any:
    settings = get_settings()
    messages_payload = cast(Any, messages)
    tools_payload = cast(Any, tools)
    if stream:
        return client.chat.stream(
            model=settings.mistral_model,
            messages=messages_payload,
            tools=tools_payload,
            tool_choice="auto",
        )

        # This is broken... See https://github.com/mistralai/client-python/issues/168
        return client.chat.complete(
            model=settings.mistral_model,
            messages=messages_payload,
            tools=tools_payload,
            stream=True,
        )

    return client.chat.complete(
        model=settings.mistral_model,
        messages=messages_payload,
        tools=tools_payload,
        tool_choice="auto",
        stream=False,
    )


def _extract_message(completion: Any) -> dict[str, Any]:
    choices = _get_attr(completion, "choices", []) or []
    if not choices:
        return {}
    first_choice = choices[0]
    message = _get_attr(first_choice, "message", {})
    return _as_dict(message)


def _run_placeholder_tool(name: str, arguments_text: str, game_id: int) -> str:
    print(f"[ai-tool] running {name}({arguments_text})")
    try:
        args = json.loads(arguments_text) if arguments_text else {}
    except json.JSONDecodeError:
        args = {"raw_arguments": arguments_text}
    try:
        if name == "get_game_state":
            result = state_tools.get_game_state(args, game_id=game_id)
        elif name == "create_live_actor":
            result = state_tools.create_live_actor(args, game_id=game_id)
        elif name == "delete_live_actor":
            result = state_tools.delete_live_actor(args, game_id=game_id)
        elif name == "change_map":
            result = state_tools.change_map(args, game_id=game_id)
        elif name == "unlock_next_chapter":
            result = state_tools.unlock_next_chapter(args, game_id=game_id)
        elif name == "change_environment_description":
            result = state_tools.change_environment_description(args, game_id=game_id)
        else:
            result = {"error": f"unknown tool '{name}'", "received": args}
    except Exception as exc:
        result = {"error": str(exc), "received": args}
    return json.dumps(result, ensure_ascii=True)


def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for call in tool_calls or []:
        as_dict = _as_dict(call)
        function_data = _as_dict(
            _get_attr(call, "function", as_dict.get("function", {}))
        )
        normalized.append(
            {
                "id": _get_attr(call, "id", as_dict.get("id")),
                "type": _get_attr(call, "type", as_dict.get("type", "function")),
                "function": {
                    "name": function_data.get("name"),
                    "arguments": function_data.get("arguments", "{}"),
                },
            }
        )
    return normalized


def _resolve_tool_calls(
    client: Mistral,
    messages: list[dict[str, Any]],
    game_id: int,
    max_rounds: int = 3,
    on_intermediate_message: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    resolved_messages = list(messages)

    for _ in range(max_rounds):
        completion = _chat_create(
            client,
            messages=resolved_messages,
            tools=TOOLS,
            stream=False,
        )
        assistant_message = _extract_message(completion)
        tool_calls = _normalize_tool_calls(assistant_message.get("tool_calls"))

        if not tool_calls:
            break

        assistant_tool_call_message = {
            "role": "assistant",
            "content": assistant_message.get("content", "") or "",
            "tool_calls": tool_calls,
        }
        resolved_messages.append(assistant_tool_call_message)
        if on_intermediate_message is not None:
            on_intermediate_message(assistant_tool_call_message)

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"] or "unknown_tool"
            tool_arguments = tool_call["function"]["arguments"] or "{}"
            tool_result = _run_placeholder_tool(tool_name, tool_arguments, game_id)
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": tool_result,
            }
            resolved_messages.append(tool_message)
            if on_intermediate_message is not None:
                on_intermediate_message(tool_message)

    return resolved_messages


def _extract_completion_text(payload: Any) -> str:
    choices = _get_attr(payload, "choices", []) or []
    if not choices:
        return ""
    first_choice = choices[0]
    message = _get_attr(first_choice, "message", {}) or {}
    content = _get_attr(message, "content", "")
    return content if isinstance(content, str) else ""


def _stream_chunks(stream_or_completion: Any) -> Iterator[str]:
    # Non-stream fallback (`chat.complete` style response)
    top_level_choices = _get_attr(stream_or_completion, "choices", None)
    if top_level_choices:
        text = _extract_completion_text(stream_or_completion)
        if text:
            yield text
        return

    # Streaming response (`chat.stream` style events)
    for event in stream_or_completion:
        chunk = _get_attr(event, "data", event)
        choices = _get_attr(chunk, "choices", []) or []
        if not choices:
            continue
        delta = _get_attr(choices[0], "delta", {}) or {}
        content = _get_attr(delta, "content")
        if isinstance(content, str) and content:
            yield content


def stream_ai_response(
    history: list[dict[str, Any]],
    game_id: int,
    on_intermediate_message: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[str]:
    client = _build_client()
    context_prompt = _build_game_context_system_message(game_id)
    messages = _resolve_tool_calls(
        client,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": context_prompt},
            *history,
        ],
        game_id,
        on_intermediate_message=on_intermediate_message,
    )
    stream = _chat_create(
        client,
        messages=messages,
        tools=TOOLS,
        stream=True,
    )
    yield from _stream_chunks(stream)
