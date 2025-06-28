from importlib import import_module
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - not packaged during tests
    sys.modules["orjson"] = object()

mod = import_module("functions.pipes.openai_responses_manifold.openai_responses_manifold")


def test_marker_utils():
    marker = mod.create_marker("function_call", ulid="01HX4Y2VW5VR2Z2H", model_id="gpt-4o")
    wrapped = mod.wrap_marker(marker)
    assert mod.contains_marker(wrapped)

    parsed = mod.parse_marker(marker)
    assert parsed["item_type"] == "function_call"
    assert parsed["metadata"]["model"] == "gpt-4o"

    text = f"hello {wrapped} world"
    assert mod.extract_markers(text, parsed=True)[0]["ulid"] == "01HX4Y2VW5VR2Z2H"
    segments = mod.split_text_by_markers(text)
    assert [s["type"] for s in segments] == ["text", "marker", "text"]


def test_persistence_and_roundtrip(monkeypatch):
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

    marker_str = mod.persist_openai_response_items(
        "c1",
        "m1",
        [{"type": "function_call", "name": "calc", "arguments": "{}"}],
        "openai_responses.gpt-4o",
    )
    item_id = mod.extract_markers(marker_str, parsed=True)[0]["ulid"]
    assert item_id in storage["c1"]["openai_responses_pipe"]["items"]

    messages = [{"role": "assistant", "content": marker_str + "ok"}]
    result = mod.ResponsesBody.transform_messages_to_input(
        messages,
        chat_id="c1",
        openwebui_model_id="openai_responses.gpt-4o",
    )
    assert result[0]["type"] == "function_call"
    assert result[1]["role"] == "assistant"
    assert result[1]["content"][0]["text"] == "ok"


def test_transform_tools():
    tools = [
        {"spec": {"name": "add", "description": ""}},
        {"type": "function", "function": {"name": "sub", "parameters": {}}},
        {"type": "web_search"},
    ]
    out = mod.ResponsesBody.transform_tools(tools, strict=True)

    keys = {t["type"] if t.get("type") != "function" else t.get("name") for t in out}
    assert keys == {"add", "sub", "web_search"}
    assert all(t.get("strict") for t in out if t.get("type") == "function")
