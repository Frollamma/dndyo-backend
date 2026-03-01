import json
import logging
import os
from urllib.parse import urlparse
from typing import Any

import http.client
import httpx
from sqlmodel import Session

from dndyo.app.core.db import engine, init_db
from dndyo.app.models.image import Image
from dndyo.app.models.map import Map


def _request(
    client: httpx.Client, method: str, path: str, payload: dict[str, Any] | None = None
):
    try:
        response = client.request(method, path, json=payload)
    except Exception as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text
        raise RuntimeError(f"{method} {path} failed ({response.status_code}): {detail}")
    return response


def _stream_request(client: httpx.Client, method: str, path: str):
    try:
        with client.stream(method, path) as response:
            if response.status_code >= 400:
                detail = response.text
                raise RuntimeError(
                    f"{method} {path} failed ({response.status_code}): {detail}"
                )

            full_text: list[str] = []
            print("ai> ", end="", flush=True)
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/event-stream" in content_type:
                for line in response.iter_lines():
                    if not line:
                        continue
                    text = line.decode("utf-8") if isinstance(line, bytes) else line
                    text = text.strip()
                    if not text.startswith("data:"):
                        continue
                    payload = text[len("data:") :].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        full_text.append(content)
                        print(content, end="", flush=True)
            else:
                for chunk in response.iter_text():
                    if not chunk:
                        continue
                    full_text.append(chunk)
                    print(chunk, end="", flush=True)
            print()
            return "".join(full_text)
    except Exception as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc


def _conn_from_base_url(base_url: str) -> http.client.HTTPConnection:
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if scheme == "https":
        return http.client.HTTPSConnection(host, port or 443, timeout=60)
    return http.client.HTTPConnection(host, port or 80, timeout=60)


def _stream_request_raw(base_url: str, method: str, path: str) -> str:
    parsed = urlparse(base_url)
    request_path = path
    if parsed.path and parsed.path != "/":
        request_path = parsed.path.rstrip("/") + path

    conn = _conn_from_base_url(base_url)
    try:
        conn.request(method, request_path)
        response = conn.getresponse()
        if response.status >= 400:
            body = response.read().decode("utf-8", "ignore")
            raise RuntimeError(
                f"{method} {path} failed ({response.status} {response.reason}): {body}"
            )

        full_text: list[str] = []
        print("ai> ", end="", flush=True)
        content_type = (response.getheader("Content-Type") or "").lower()

        if "text/event-stream" in content_type:
            while True:
                line = response.fp.readline()
                if not line:
                    break
                text = line.decode("utf-8", "ignore").strip()
                if not text or not text.startswith("data:"):
                    continue
                payload = text[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    full_text.append(content)
                    print(content, end="", flush=True)
        else:
            body = response.read().decode("utf-8", "ignore")
            if body:
                full_text.append(body)
                print(body, end="", flush=True)

        print()
        return "".join(full_text)
    except Exception as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc
    finally:
        conn.close()


def _seed_image(uri: str) -> int:
    with Session(engine) as session:
        image = Image(uri=uri)
        session.add(image)
        session.commit()
        session.refresh(image)
        if image.id is None:
            raise RuntimeError("Image ID was not generated.")
        return image.id


def _create_actor(
    client: httpx.Client, game_id: int, *, name: str, role: str, image_id: int
) -> int:
    actor_payload = {
        "name": name,
        "level": 3 if role == "Player" else 2,
        "armor_class": 15 if role == "Player" else 13,
        "hit_points": 24 if role == "Player" else 16,
        "speed": 30,
        "strength": 12,
        "dexterity": 14,
        "constitution": 12,
        "intelligence": 10,
        "wisdom": 12,
        "charisma": 10,
        "proficiency_bonus": 2,
        "size": "Medium",
        "alignment": "Neutral Good" if role == "Player" else "Chaotic Evil",
        "controlled_by_user": role == "Player",
        "can_fight": True,
        "image_id": image_id,
        "abilities": [
            {
                "name": "Basic Attack",
                "description": "A straightforward weapon strike.",
                "ability_type": "attack",
            }
        ],
    }
    response = _request(
        client,
        "POST",
        f"/api/game/{game_id}/actor/actor",
        actor_payload,
    )
    return int(response.json()["id"])


def _seed_map(*, game_id: int, name: str, image_id: int) -> int:
    with Session(engine) as session:
        db_map = Map(
            game_id=game_id,
            name=name,
            description=0,
            image_id=image_id,
            connected_maps_ids=[],
        )
        session.add(db_map)
        session.commit()
        session.refresh(db_map)
        if db_map.id is None:
            raise RuntimeError("Map ID was not generated.")
        return db_map.id


def _seed_game(client: httpx.Client) -> int:
    game_response = _request(
        client,
        "POST",
        "/api/game/",
        {
            "name": "Ashfall Keep",
            "owner_user": "manual-tui",
            "chapters": [
                "Chapter 1: Smoke Over Blackridge",
                "Chapter 2: The Broken Gate",
                "Chapter 3: Crown of Cinders",
            ],
            "current_chapters": ["Chapter 1: Smoke Over Blackridge"],
            "initial_state": {
                "world_state": "Ash is drifting across Blackridge. The keep bells are silent.",
                "live_actors": [],
            },
        },
    )
    game_id = int(game_response.json()["id"])

    image_ids = [
        _seed_image("https://example.com/blackridge-gate-map.png"),
        _seed_image("https://example.com/lyra.png"),
        _seed_image("https://example.com/dorn.png"),
        _seed_image("https://example.com/goblin.png"),
        _seed_image("https://example.com/wolf.png"),
    ]

    blackridge_gate_map_id = _seed_map(
        game_id=game_id,
        name="Blackridge Gate",
        image_id=image_ids[0],
    )
    _request(
        client,
        "PATCH",
        f"/api/game/{game_id}/state/current-map",
        {"current_map_id": blackridge_gate_map_id},
    )

    lyra_id = _create_actor(
        client, game_id, name="Lyra Voss", role="Player", image_id=image_ids[1]
    )
    dorn_id = _create_actor(
        client, game_id, name="Dorn Hale", role="Player", image_id=image_ids[2]
    )
    goblin_id = _create_actor(
        client, game_id, name="Skreek", role="Enemy", image_id=image_ids[3]
    )
    wolf_id = _create_actor(
        client, game_id, name="Ashfang", role="Enemy", image_id=image_ids[4]
    )

    _request(
        client,
        "PUT",
        f"/api/game/{game_id}/state/live-actors",
        {
            "live_actors": [
                {
                    "actor_id": lyra_id,
                    "current_hp": 24,
                    "state": "Ready, calm, scanning rooftops",
                    "background": "Former city scout who lost her unit in a border ambush.",
                    "role": "Player",
                },
                {
                    "actor_id": dorn_id,
                    "current_hp": 26,
                    "state": "Shield raised near the gate",
                    "background": "Ex-guard captain seeking redemption after abandoning his post.",
                    "role": "Player",
                },
                {
                    "actor_id": goblin_id,
                    "current_hp": 16,
                    "state": "Hiding behind rubble with a shortbow",
                    "background": "Raider from the red-claw tribe, loyal only to coin.",
                    "role": "Enemy",
                },
                {
                    "actor_id": wolf_id,
                    "current_hp": 14,
                    "state": "Circling and sniffing for blood",
                    "background": "War-trained dire wolf scarred by years of sieges.",
                    "role": "Enemy",
                },
            ]
        },
    )
    print(f"Seeded game id: {game_id}")
    print("Story: Chapter 1: Smoke Over Blackridge")
    print("Players:")
    print("  - Lyra Voss: Former city scout who lost her unit in a border ambush.")
    print(
        "  - Dorn Hale: Ex-guard captain seeking redemption after abandoning his post."
    )
    print("Enemies:")
    print("  - Skreek: Raider from the red-claw tribe, loyal only to coin.")
    print("  - Ashfang: War-trained dire wolf scarred by years of sieges.")
    return game_id


def _print_help():
    print("Commands:")
    print("  /help     Show commands")
    print("  /state    Print current game state")
    print("  /history  Print chat history")
    print("  /ai       Run AI on current chat history")
    print("  /quit     Exit")
    print("Any other text sends a user chat message.")


def main():
    # Keep manual testing output readable.
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    init_db()
    base_url = os.environ.get("DNDYO_API_URL", "http://127.0.0.1:8000")

    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        _request(client, "GET", "/health")
        game_id = _seed_game(client)
        print("Type /help for commands.")

        while True:
            user_input = input("you> ").strip()
            if not user_input:
                continue

            if user_input == "/quit":
                print("Bye.")
                return
            if user_input == "/help":
                _print_help()
                continue
            if user_input == "/state":
                state = _request(client, "GET", f"/api/game/{game_id}/state").json()
                print(json.dumps(state, indent=2))
                continue
            if user_input == "/history":
                messages = _request(
                    client, "GET", f"/api/game/{game_id}/chat/messages"
                ).json()
                for message in messages:
                    role = message["message"]["role"]
                    content = message["message"]["content"]
                    print(f"{role}> {content}")
                continue
            if user_input == "/ai":
                try:
                    _stream_request(
                        client, "POST", f"/api/game/{game_id}/chat/run-ai"
                    )
                except RuntimeError as exc:
                    print(f"ai-error> {exc}")
                    continue
                continue
            if user_input.startswith("/"):
                print("Unknown command. Use /help.")
                continue

            _request(
                client,
                "POST",
                f"/api/game/{game_id}/chat/message",
                {"message": {"role": "user", "content": user_input}},
            )
            print("saved.")
