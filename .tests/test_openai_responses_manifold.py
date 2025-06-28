from importlib import import_module
import json
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    sys.modules["orjson"] = object()

mod = import_module("functions.pipes.openai_responses_manifold.openai_responses_manifold")


def test_marker_roundtrip():
    marker = mod.create_marker("function_call", ulid="01HX4Y2VW5VR2Z2H", model_id="gpt-4o")
    wrapped = mod.wrap_marker(marker)
    assert mod.contains_marker(wrapped)

    parsed = mod.parse_marker(marker)
    assert parsed["metadata"]["model"] == "gpt-4o"

    text = f"pre {wrapped} post"
    assert mod.extract_markers(text) == [marker]

    segments = mod.split_text_by_markers(text)
    assert segments[1] == {"type": "marker", "marker": marker}
    assert segments[0]["text"].startswith("pre")
    assert segments[-1]["text"].strip().endswith("post")


def test_persistence_fetch_and_input(monkeypatch):
    storage = {}

    class DummyChatModel:
        def __init__(self, chat=None):
            self.chat = chat or {"history": {"messages": {}}}

    class DummyChats:
        @staticmethod
        def get_chat_by_id(cid):
            return DummyChatModel(storage.get(cid, {"history": {"messages": {}}}))

        @staticmethod
        def update_chat_by_id(cid, chat):
            storage[cid] = chat
            return DummyChatModel(chat)

    monkeypatch.setattr(mod, "Chats", DummyChats)

    marker1 = mod.persist_openai_response_items(
        "c1",
        "m1",
        [{"type": "function_call", "name": "calc", "arguments": "{}"}],
        "openai_responses.gpt-4o",
    )
    marker2 = mod.persist_openai_response_items(
        "c1",
        "m2",
        [{"type": "function_call", "name": "other", "arguments": "{}"}],
        "openai_responses.gpt-3.5",
    )

    uid1 = mod.extract_markers(marker1, parsed=True)[0]["ulid"]
    uid2 = mod.extract_markers(marker2, parsed=True)[0]["ulid"]

    fetched = mod.fetch_openai_response_items(
        "c1", [uid1, uid2], openwebui_model_id="openai_responses.gpt-4o"
    )
    assert list(fetched) == [uid1]

    messages = [{"role": "assistant", "content": marker1 + "ok"}]
    output = mod.ResponsesBody.transform_messages_to_input(
        messages,
        chat_id="c1",
        openwebui_model_id="openai_responses.gpt-4o",
    )
    assert output[0]["type"] == "function_call"
    assert output[1]["content"][0]["text"] == "ok"


def test_tool_transforms_and_mcp():
    tools = [
        {"spec": {"name": "add", "description": "", "parameters": {}}},
        {"type": "function", "function": {"name": "add", "parameters": {}}},
        {"type": "web_search"},
    ]
    out = mod.ResponsesBody.transform_tools(tools, strict=True)
    names = {t.get("name", t.get("type")) for t in out}
    assert names == {"add", "web_search"}
    for t in out:
        if t.get("type") == "function":
            assert t["strict"] is True
            assert t["parameters"]["additionalProperties"] is False

    mcp_json = json.dumps({"server_label": "main", "server_url": "https://x.y"})
    assert mod.ResponsesBody._build_mcp_tools(mcp_json) == [
        {"type": "mcp", "server_label": "main", "server_url": "https://x.y"}
    ]
