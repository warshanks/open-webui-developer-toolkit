from importlib import import_module
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - not packaged during tests
    sys.modules["orjson"] = object()

def test_importable():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')
    assert hasattr(mod, 'Pipe')


def test_history_filters_by_model(monkeypatch):
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')
    ChatModel = import_module('open_webui.models.chats').ChatModel

    # Patch get_message_list to return the requested message only
    monkeypatch.setattr(mod, "get_message_list", lambda hist, mid: [hist[mid]])

    chat = {
        "history": {
            "currentId": "msg1",
            "messages": {
                "msg1": {
                    "id": "msg1",
                    "role": "user",
                    "content": "hello",
                    "parentId": None,
                    "childrenIds": [],
                }
            },
        },
        "openai_responses_pipe": {
            "messages": {
                "msg1": [
                    {"type": "reasoning", "encrypted_content": "A", "model": "x"},
                    {"type": "reasoning", "encrypted_content": "B", "model": "y"},
                ]
            }
        },
    }

    monkeypatch.setattr(mod.Chats, "get_chat_by_id", lambda cid: ChatModel(chat) if cid == "c" else None)

    res_x = mod.build_responses_history_by_chat_id_and_message_id("c", "msg1", model_id="x")
    assert any(item.get("encrypted_content") == "A" for item in res_x)
    assert all(item.get("encrypted_content") != "B" for item in res_x)

    res_y = mod.build_responses_history_by_chat_id_and_message_id("c", "msg1", model_id="y")
    assert any(item.get("encrypted_content") == "B" for item in res_y)
    assert all(item.get("encrypted_content") != "A" for item in res_y)
