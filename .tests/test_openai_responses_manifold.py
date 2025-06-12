from importlib import import_module
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - not packaged during tests
    sys.modules["orjson"] = object()

def test_importable():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')
    assert hasattr(mod, 'Pipe')


def test_encode_decode_roundtrip():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

    sample_id = "01HX4Y2VW5VR2Z2HDQ5QY9REHB"
    encoded = mod.encode_id(sample_id)
    assert mod.decode_id(encoded) == sample_id


def test_split_and_extract_ids():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

    ids = [
        "01HX4Y2VW5VR2Z2HDQ5QY9REHB",
        "01HX4Y2VW6B091XE84F5G0Z8NF",
    ]
    encoded = "".join(mod.encode_id(i) for i in ids)
    content = f"prefix {encoded} suffix"

    assert mod.extract_encoded_ids(content) == ids

    segments = mod.split_content_by_encoded_ids(content)
    assert segments[0]["type"] == "text"
    assert segments[1]["type"] == "encoded_id"
    assert segments[1]["id"] == ids[0]
    assert segments[2]["type"] == "encoded_id"
    assert segments[2]["id"] == ids[1]
    assert segments[3]["type"] == "text"


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

    encoded = mod.add_openai_response_items_and_get_encoded_ids(
        "c1",
        "m1",
        [{"type": "function_call", "name": "calc", "arguments": "{}"}],
        "openai_responses.gpt-4o",
    )
    assert encoded  # id encoded
    stored_id = mod.extract_encoded_ids(encoded)[0]
    assert (
        storage["c1"]["openai_responses_pipe"]["items"][stored_id]["model"]
        == "openai_responses.gpt-4o"
    )

    messages = [{"role": "assistant", "content": encoded + "result"}]
    result = mod.build_openai_input(messages, "c1", model_id="openai_responses.gpt-4o")

    assert result[0]["type"] == "function_call"
    assert result[1]["type"] == "message"
    assert result[1]["content"][0]["text"] == "result"
