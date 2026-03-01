import json
from collections.abc import Iterable, Iterator
from typing import Any, cast

from mistralai import Mistral

from dndyo.app.core.config import get_settings
from dndyo.app.core.ai.tools import state as state_tools

TOOLS = state_tools.TOOLS
SYSTEM_PROMPT = (
    "You are the Dungeon Master of a Dungeons & Dragons game. "
    "Lead the game, narrate scenes, control pacing, and guide players through "
    "decisions and outcomes. "
    "You can access tools to inspect and update game state; use those tools when "
    "needed to keep the world state accurate."
)


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
    chat_api = client.chat
    completions_api = getattr(chat_api, "completions", None)
    if completions_api and hasattr(completions_api, "create"):
        return completions_api.create(
            model=settings.mistral_model,
            messages=messages_payload,
            tools=tools_payload,
            stream=stream,
        )
    if stream and hasattr(chat_api, "stream"):
        return chat_api.stream(
            model=settings.mistral_model,
            messages=messages_payload,
            tools=tools_payload,
        )
    return chat_api.complete(
        model=settings.mistral_model,
        messages=messages_payload,
        tools=tools_payload,
    )


def _extract_message(completion: Any) -> dict[str, Any]:
    choices = _get_attr(completion, "choices", []) or []
    if not choices:
        return {}
    first_choice = choices[0]
    message = _get_attr(first_choice, "message", {})
    return _as_dict(message)


def _run_placeholder_tool(name: str, arguments_text: str, game_id: int) -> str:
    try:
        args = json.loads(arguments_text) if arguments_text else {}
    except json.JSONDecodeError:
        args = {"raw_arguments": arguments_text}
    try:
        if name == "get_state":
            result = state_tools.get_state(args, game_id=game_id)
        elif name == "create_live_actor":
            result = state_tools.create_live_actor(args, game_id=game_id)
        elif name == "delete_live_actor":
            result = state_tools.delete_live_actor(args, game_id=game_id)
        elif name == "change_map":
            result = state_tools.change_map(args, game_id=game_id)
        elif name == "unlock_next_chapter":
            result = state_tools.unlock_next_chapter(args, game_id=game_id)
        elif name == "change_world_state":
            result = state_tools.change_world_state(args, game_id=game_id)
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

        resolved_messages.append(
            {
                "role": "assistant",
                "content": assistant_message.get("content", "") or "",
                "tool_calls": tool_calls,
            }
        )

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"] or "unknown_tool"
            tool_arguments = tool_call["function"]["arguments"] or "{}"
            tool_result = _run_placeholder_tool(tool_name, tool_arguments, game_id)
            resolved_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_name,
                    "content": tool_result,
                }
            )

    return resolved_messages


def _stream_chunks(stream: Iterable[Any]) -> Iterator[str]:
    for event in stream:
        chunk = _get_attr(event, "data", event)
        choices = _get_attr(chunk, "choices", []) or []
        if not choices:
            continue
        delta = _get_attr(choices[0], "delta", {}) or {}
        content = _get_attr(delta, "content")
        if isinstance(content, str) and content:
            yield content


def stream_ai_response(history: list[dict[str, Any]], game_id: int) -> Iterator[str]:
    client = _build_client()
    messages = _resolve_tool_calls(
        client,
        [{"role": "system", "content": SYSTEM_PROMPT}, *history],
        game_id,
    )
    stream = _chat_create(
        client,
        messages=messages,
        tools=TOOLS,
        stream=True,
    )
    yield from _stream_chunks(stream)
