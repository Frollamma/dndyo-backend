import json

from dndyo.app.core.ai import ai


def test_stream_ai_response_resolves_tool_calls_and_streams(monkeypatch):
    client = object()
    chat_calls: list[dict] = []
    tool_calls_seen: list[tuple[str, str, int]] = []

    def fake_build_client():
        return client

    first_completion = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "change_environment_description",
                                "arguments": json.dumps({"description": "Rain begins"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    second_completion = {
        "choices": [
            {
                "message": {
                    "content": "Tool call complete.",
                    "tool_calls": [],
                }
            }
        ]
    }
    stream_events = [
        {"data": {"choices": [{"delta": {"content": "Final "}}]}},
        {"data": {"choices": [{"delta": {"content": "answer"}}]}},
    ]

    def fake_chat_create(_client, *, messages, tools=None, stream=False):
        chat_calls.append({"messages": messages, "tools": tools, "stream": stream})
        if stream:
            return stream_events
        if len(chat_calls) == 1:
            return first_completion
        return second_completion

    def fake_run_tool(name: str, arguments_text: str, game_id: int) -> str:
        tool_calls_seen.append((name, arguments_text, game_id))
        return json.dumps({"ok": True, "tool": name})

    monkeypatch.setattr(ai, "_build_client", fake_build_client)
    monkeypatch.setattr(ai, "_chat_create", fake_chat_create)
    monkeypatch.setattr(ai, "_run_placeholder_tool", fake_run_tool)
    monkeypatch.setattr(
        ai,
        "_get_game_initial_prompt",
        lambda game_id: f"Initial prompt for {game_id}",
    )
    monkeypatch.setattr(
        ai,
        "_build_game_context_system_message",
        lambda game_id: f"Game context for {game_id}",
    )

    result = "".join(
        ai.stream_ai_response(
            history=[{"role": "user", "content": "Change weather and narrate."}],
            game_id=42,
        )
    )

    assert result == "Final answer"
    assert tool_calls_seen == [
        (
            "change_environment_description",
            '{"description": "Rain begins"}',
            42,
        )
    ]
    assert len(chat_calls) == 3
    assert chat_calls[0]["stream"] is False
    assert chat_calls[1]["stream"] is False
    assert chat_calls[2]["stream"] is True
    first_messages = chat_calls[0]["messages"]
    assert first_messages[0]["role"] == "system"
    assert first_messages[0]["content"] == "Initial prompt for 42"
    assert first_messages[1]["role"] == "system"
    assert first_messages[1]["content"] == "Game context for 42"

    # The second resolution request should include a "tool" role message.
    second_messages = chat_calls[1]["messages"]
    assert any(message["role"] == "tool" for message in second_messages)


def test_run_placeholder_tool_unknown_name_returns_error_json():
    payload = json.loads(
        ai._run_placeholder_tool("nonexistent_tool", '{"x":1}', game_id=1)
    )
    assert payload["error"] == "unknown tool 'nonexistent_tool'"
    assert payload["received"] == {"x": 1}
