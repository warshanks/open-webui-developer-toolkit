from importlib import import_module
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - not packaged during tests
    sys.modules["orjson"] = object()

def test_importable():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')
    assert hasattr(mod, 'Pipe')


def test_marker_roundtrip():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

    marker = mod.create_marker('function_call', ulid='01HX4Y2VW5VR2Z2H', model_id='gpt-4o')
    parsed = mod.parse_marker(marker)
    assert parsed['ulid'] == '01HX4Y2VW5VR2Z2H'
    assert parsed['item_type'] == 'function_call'
    assert parsed['metadata']['model'] == 'gpt-4o'
    wrapped = mod.wrap_marker(marker)
    assert wrapped.startswith('\n[openai_responses:v2:') and wrapped.endswith(']: #\n')


def test_split_and_extract_markers():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

    ids = [
        "01HX4Y2VW5VR2Z2H",
        "01HX4Y2VW6B091XE",
    ]
    encoded = "".join(mod.wrap_marker(mod.create_marker('function_call', ulid=i)) for i in ids)
    content = f"prefix {encoded} suffix"

    extracted = mod.extract_markers(content)
    assert all(id in m for id, m in zip(ids, extracted))

    segments = mod.split_text_by_markers(content)
    assert segments[0]["type"] == "text"
    assert segments[1]["type"] == "marker"
    assert 'openai_responses:v2:function_call' in segments[1]['marker']


def test_item_persistence_roundtrip(monkeypatch):
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

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

    encoded = mod.persist_openai_response_items(
        "c1",
        "m1",
        [{"type": "function_call", "name": "calc", "arguments": "{}"}],
        "openai_responses.gpt-4o",
    )
    assert encoded
    stored_id = mod.extract_markers(encoded, parsed=True)[0]["ulid"]
    assert (
        storage["c1"]["openai_responses_pipe"]["items"][stored_id]["model"]
        == "openai_responses.gpt-4o"
    )

    messages = [{"role": "assistant", "content": encoded + "result"}]
    result = mod.ResponsesBody.transform_messages_to_input(
        messages, chat_id="c1", openwebui_model_id="openai_responses.gpt-4o"
    )

    assert result[0]["type"] == "function_call"
    assert result[1]["role"] == "assistant"
    assert result[1]["content"][0]["text"] == "result"
