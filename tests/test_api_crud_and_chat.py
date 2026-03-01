from sqlmodel import Session

from dndyo.app.models.image import Image


def _create_game(client) -> int:
    response = client.post(
        "/api/game/",
        json={
            "name": "Campaign One",
            "owner_user": "owner-1",
            "ai_initial_prompt": "Test DM prompt.",
            "chapters": ["c1", "c2"],
            "current_chapters": [],
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_live_actor(client, test_engine, game_id: int, *, name: str = "Lyra") -> int:
    with Session(test_engine) as session:
        image = Image(uri=f"https://example.com/{name.lower()}.png")
        session.add(image)
        session.commit()
        session.refresh(image)
        assert image.id is not None
        image_id = image.id

    actor = client.post(
        f"/api/game/{game_id}/actor/actor",
        json={
            "name": name,
            "level": 3,
            "armor_class": 14,
            "hit_points": 20,
            "speed": 30,
            "strength": 10,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 11,
            "proficiency_bonus": 2,
            "size": "Medium",
            "alignment": "Neutral Good",
            "controlled_by_user": True,
            "can_fight": True,
            "image_id": image_id,
            "abilities": [],
        },
    )
    assert actor.status_code == 200
    actor_id = actor.json()["id"]

    state = client.put(
        f"/api/game/{game_id}/state/live-actors",
        json={
            "live_actors": [
                {
                    "actor_id": actor_id,
                    "current_hp": 20,
                    "state": "Ready",
                    "background": "Scout",
                    "role": "Player",
                }
            ]
        },
    )
    assert state.status_code == 200
    return state.json()["live_actors"][0]["id"]


def test_game_create_and_read_endpoints(client):
    game_id = _create_game(client)

    get_one = client.get(f"/api/game/{game_id}")
    assert get_one.status_code == 200
    assert get_one.json()["id"] == game_id
    assert get_one.json()["name"] == "Campaign One"

    get_all = client.get("/api/game/")
    assert get_all.status_code == 200
    payload = get_all.json()
    assert len(payload) == 1
    assert payload[0]["id"] == game_id


def test_game_create_accepts_initial_state(client):
    response = client.post(
        "/api/game/",
        json={
            "name": "Campaign Two",
            "owner_user": "owner-2",
            "ai_initial_prompt": "Initial prompt for campaign two.",
            "chapters": ["intro"],
            "current_chapters": [],
            "initial_state": {
                "environment_description": "The tavern is crowded and loud.",
                "current_map_id": None,
                "live_actors": [],
            },
        },
    )
    assert response.status_code == 200
    game_id = response.json()["id"]

    state = client.get(f"/api/game/{game_id}/state")
    assert state.status_code == 200
    assert state.json()["environment_description"] == "The tavern is crowded and loud."
    assert state.json()["live_actors"] == []
    assert isinstance(state.json()["current_map_id"], int)
    assert state.json()["current_map_id"] > 0


def test_state_update_and_read(client):
    game_id = _create_game(client)

    update = client.patch(
        f"/api/game/{game_id}/state/environment-description",
        json={"environment_description": "Night falls over the valley."},
    )
    assert update.status_code == 200
    assert update.json()["environment_description"] == "Night falls over the valley."

    read = client.get(f"/api/game/{game_id}/state")
    assert read.status_code == 200
    assert read.json()["environment_description"] == "Night falls over the valley."


def test_chat_message_crud(client, test_engine):
    game_id = _create_game(client)
    sender_id = _create_live_actor(client, test_engine, game_id)

    create_user = client.post(
        f"/api/game/{game_id}/chat/message",
        json={
            "sender_id": sender_id,
            "message": {"role": "user", "content": "Hello DM"},
        },
    )
    assert create_user.status_code == 200
    assert create_user.json()["message"]["content"] == "Hello DM"

    create_system = client.post(
        f"/api/game/{game_id}/chat/message",
        json={
            "sender_id": sender_id,
            "message": {"role": "system", "content": "Session setup"},
        },
    )
    assert create_system.status_code == 200

    read = client.get(f"/api/game/{game_id}/chat/messages")
    assert read.status_code == 200
    payload = read.json()
    assert [msg["message"]["role"] for msg in payload] == ["user", "system"]

    deleted = client.delete(f"/api/game/{game_id}/chat/messages")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": 2}

    read_after_delete = client.get(f"/api/game/{game_id}/chat/messages")
    assert read_after_delete.status_code == 200
    assert read_after_delete.json() == []


def test_chat_message_rejects_unknown_live_actor_sender(client):
    game_id = _create_game(client)
    response = client.post(
        f"/api/game/{game_id}/chat/message",
        json={"sender_id": 9999, "message": {"role": "user", "content": "Hello DM"}},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Live actor 9999 does not exist in game {game_id}."
    )


def test_chat_message_rejects_non_system_without_sender_id(client):
    game_id = _create_game(client)
    response = client.post(
        f"/api/game/{game_id}/chat/message",
        json={"message": {"role": "user", "content": "Hello DM"}},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "sender_id is required for user messages unless content starts with 'Dev:'."
    )


def test_chat_message_accepts_system_without_sender_id(client):
    game_id = _create_game(client)
    response = client.post(
        f"/api/game/{game_id}/chat/message",
        json={"message": {"role": "system", "content": "Session setup"}},
    )
    assert response.status_code == 200
    assert response.json()["sender_id"] is None
    assert response.json()["message"]["role"] == "system"


def test_chat_message_accepts_dev_prefixed_user_without_sender_id(client):
    game_id = _create_game(client)
    response = client.post(
        f"/api/game/{game_id}/chat/message",
        json={"message": {"role": "user", "content": "Dev: Session setup"}},
    )
    assert response.status_code == 200
    assert response.json()["sender_id"] is None
    assert response.json()["message"]["role"] == "user"
