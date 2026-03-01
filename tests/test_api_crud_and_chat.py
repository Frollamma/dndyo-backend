def _create_game(client) -> int:
    response = client.post(
        "/api/game/",
        json={
            "name": "Campaign One",
            "owner_user": "owner-1",
            "chapters": ["c1", "c2"],
            "current_chapters": [],
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


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
            "chapters": ["intro"],
            "current_chapters": [],
            "initial_state": {
                "world_state": "The tavern is crowded and loud.",
                "current_map_id": None,
                "live_actors": [],
            },
        },
    )
    assert response.status_code == 200
    game_id = response.json()["id"]

    state = client.get(f"/api/game/{game_id}/state")
    assert state.status_code == 200
    assert state.json()["world_state"] == "The tavern is crowded and loud."
    assert state.json()["live_actors"] == []
    assert isinstance(state.json()["current_map_id"], int)
    assert state.json()["current_map_id"] > 0


def test_state_update_and_read(client):
    game_id = _create_game(client)

    update = client.patch(
        f"/api/game/{game_id}/state/world-state",
        json={"world_state": "Night falls over the valley."},
    )
    assert update.status_code == 200
    assert update.json()["world_state"] == "Night falls over the valley."

    read = client.get(f"/api/game/{game_id}/state")
    assert read.status_code == 200
    assert read.json()["world_state"] == "Night falls over the valley."


def test_chat_message_crud(client):
    game_id = _create_game(client)

    create_user = client.post(
        f"/api/game/{game_id}/chat/message",
        json={"message": {"role": "user", "content": "Hello DM"}},
    )
    assert create_user.status_code == 200
    assert create_user.json()["message"]["content"] == "Hello DM"

    create_system = client.post(
        f"/api/game/{game_id}/chat/message",
        json={"message": {"role": "system", "content": "Session setup"}},
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
