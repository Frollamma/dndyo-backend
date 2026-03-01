from collections.abc import Iterator

from sqlmodel import Session, select

from dndyo.app.models.actor import Actor, Alignment, Size
from dndyo.app.models.image import Image
from dndyo.app.models.live_actor import LiveActor, LiveActorRole


def _create_game(client) -> int:
    response = client.post(
        "/api/game/",
        json={
            "name": "Critical Path",
            "owner_user": "tester",
            "ai_initial_prompt": "Test flow prompt.",
            "chapters": ["prologue"],
            "current_chapters": [],
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _seed_actor_and_live_actor(
    test_engine, game_id: int, *, hp: int = 20, ac: int = 12
) -> int:
    with Session(test_engine) as session:
        image = Image(uri="https://example.com/goblin.png")
        session.add(image)
        session.commit()
        session.refresh(image)
        assert image.id is not None

        actor = Actor(
            game_id=game_id,
            name="Goblin",
            level=1,
            armor_class=ac,
            hit_points=hp,
            speed=30,
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=8,
            wisdom=8,
            charisma=8,
            proficiency_bonus=2,
            size=Size.small,
            alignment=Alignment.chaotic_evil,
            controlled_by_user=False,
            can_fight=True,
            image_id=image.id,
            abilities=[],
        )
        session.add(actor)
        session.commit()
        session.refresh(actor)
        assert actor.id is not None

        live_actor = LiveActor(
            game_id=game_id,
            actor_id=actor.id,
            current_hp=hp,
            state="Alert",
            background="A snarling goblin scout from the eastern caves.",
            role=LiveActorRole.enemy,
        )
        session.add(live_actor)
        session.commit()
        session.refresh(live_actor)
        assert live_actor.id is not None
        return live_actor.id


def _seed_actor(test_engine, game_id: int, *, hp: int = 20, ac: int = 12) -> int:
    with Session(test_engine) as session:
        image = Image(uri="https://example.com/ranger.png")
        session.add(image)
        session.commit()
        session.refresh(image)
        assert image.id is not None

        actor = Actor(
            game_id=game_id,
            name="Ranger",
            level=3,
            armor_class=ac,
            hit_points=hp,
            speed=30,
            strength=10,
            dexterity=16,
            constitution=12,
            intelligence=10,
            wisdom=14,
            charisma=10,
            proficiency_bonus=2,
            size=Size.medium,
            alignment=Alignment.neutral_good,
            controlled_by_user=True,
            can_fight=True,
            image_id=image.id,
            abilities=[],
        )
        session.add(actor)
        session.commit()
        session.refresh(actor)
        assert actor.id is not None
        return actor.id


def test_create_game_and_default_state(client):
    game_id = _create_game(client)

    response = client.get(f"/api/game/{game_id}/state")
    assert response.status_code == 200
    payload = response.json()
    assert payload["live_actors"] == []
    assert isinstance(payload["current_map_id"], int)
    assert payload["current_map_id"] > 0
    assert payload["environment_description"] == ""


def test_run_ai_stream_uses_mock_and_persists_message(client, test_engine, monkeypatch):
    game_id = _create_game(client)
    sender_id = _seed_actor_and_live_actor(test_engine, game_id)
    add_user = client.post(
        f"/api/game/{game_id}/chat/message",
        json={
            "sender_id": sender_id,
            "message": {"role": "user", "content": "Set the scene."},
        },
    )
    assert add_user.status_code == 200

    def fake_stream(_history: list[dict], game_id: int) -> Iterator[str]:
        assert game_id > 0
        yield "The fog parts. "
        yield "A ruined keep looms."

    monkeypatch.setattr(
        "dndyo.app.routers.game.chat.stream_ai_response",
        fake_stream,
    )

    ai_response = client.post(f"/api/game/{game_id}/chat/run-ai")
    assert ai_response.status_code == 200
    assert ai_response.text == "The fog parts. A ruined keep looms."

    messages = client.get(f"/api/game/{game_id}/chat/messages")
    assert messages.status_code == 200
    payload = messages.json()
    assert len(payload) == 2
    assert payload[0]["message"]["role"] == "user"
    assert payload[1]["message"] == {
        "role": "assistant",
        "content": "The fog parts. A ruined keep looms.",
    }


def test_run_ai_stream_failure_does_not_break_response_and_persists_partial(
    client, test_engine, monkeypatch
):
    game_id = _create_game(client)
    sender_id = _seed_actor_and_live_actor(test_engine, game_id)
    add_user = client.post(
        f"/api/game/{game_id}/chat/message",
        json={
            "sender_id": sender_id,
            "message": {"role": "user", "content": "What do I see?"},
        },
    )
    assert add_user.status_code == 200

    def failing_stream(_history: list[dict], game_id: int) -> Iterator[str]:
        assert game_id > 0
        yield "Fog drifts over the stones. "
        raise RuntimeError("upstream stream interrupted")

    monkeypatch.setattr(
        "dndyo.app.routers.game.chat.stream_ai_response",
        failing_stream,
    )

    ai_response = client.post(f"/api/game/{game_id}/chat/run-ai")
    assert ai_response.status_code == 200
    assert "Fog drifts over the stones." in ai_response.text
    assert "[ai-stream-error] upstream stream interrupted" in ai_response.text

    messages = client.get(f"/api/game/{game_id}/chat/messages")
    assert messages.status_code == 200
    payload = messages.json()
    assert len(payload) == 2
    assert payload[1]["message"]["role"] == "assistant"
    assert payload[1]["message"]["content"] == "Fog drifts over the stones."


def test_update_live_actors_rejects_unknown_actor(client):
    game_id = _create_game(client)

    response = client.put(
        f"/api/game/{game_id}/state/live-actors",
        json={
            "live_actors": [
                {
                    "actor_id": 9999,
                    "current_hp": 10,
                    "state": "Ready",
                    "role": "Enemy",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == f"Actor 9999 does not exist in game {game_id}."


def test_update_live_actors_persists_background(client, test_engine):
    game_id = _create_game(client)
    actor_id = _seed_actor(test_engine, game_id)

    response = client.put(
        f"/api/game/{game_id}/state/live-actors",
        json={
            "live_actors": [
                {
                    "actor_id": actor_id,
                    "current_hp": 17,
                    "state": "Watching the treeline",
                    "background": "Veteran scout who survived the Blackfen war.",
                    "role": "Player",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_actors"][0]["background"] == (
        "Veteran scout who survived the Blackfen war."
    )
    assert payload["live_actors"][0]["actor"]["id"] == actor_id
    assert payload["live_actors"][0]["actor"]["name"] == "Ranger"


def test_attack_live_actor_hit_applies_damage(client, test_engine, monkeypatch):
    game_id = _create_game(client)
    live_actor_id = _seed_actor_and_live_actor(test_engine, game_id, hp=20, ac=12)

    rolls = iter([15, 4, 6])
    monkeypatch.setattr(
        "dndyo.app.routers.game.state.random.randint",
        lambda _a, _b: next(rolls),
    )

    response = client.post(
        f"/api/game/{game_id}/state/attack-live-actor",
        json={
            "live_actor_id": live_actor_id,
            "attack_bonus": 2,
            "damage_num_dice": 2,
            "damage_dice_faces": 6,
            "damage_bonus": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hit"] is True
    assert payload["critical"] is False
    assert payload["damage_rolls"] == [4, 6]
    assert payload["damage"] == 13
    assert payload["remaining_hp"] == 7


def test_attack_live_actor_miss_does_not_change_hp(client, test_engine, monkeypatch):
    game_id = _create_game(client)
    live_actor_id = _seed_actor_and_live_actor(test_engine, game_id, hp=18, ac=18)

    monkeypatch.setattr(
        "dndyo.app.routers.game.state.random.randint",
        lambda _a, _b: 2,
    )

    response = client.post(
        f"/api/game/{game_id}/state/attack-live-actor",
        json={
            "live_actor_id": live_actor_id,
            "attack_bonus": 0,
            "damage_num_dice": 1,
            "damage_dice_faces": 8,
            "damage_bonus": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hit"] is False
    assert payload["damage_rolls"] == []
    assert payload["damage"] == 0
    assert payload["remaining_hp"] == 18

    with Session(test_engine) as session:
        live_actor = session.exec(
            select(LiveActor).where(LiveActor.id == live_actor_id)
        ).first()
        assert live_actor is not None
        assert live_actor.current_hp == 18


def test_game_not_found_returns_404(client):
    response = client.get("/api/game/99999/state")
    assert response.status_code == 404
    assert response.json()["detail"] == "Game 99999 not found."
