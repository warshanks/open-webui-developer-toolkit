import types
import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def dummy_chat(monkeypatch):
    """Provide a dummy chat object and patch ``open_webui`` imports."""
    chat = {"history": {"currentId": None, "messages": {}}}

    def get_chat_by_id(_):
        return types.SimpleNamespace(chat=chat)

    def get_message_by_id_and_message_id(_, message_id):
        return chat["history"].get("messages", {}).get(message_id, {})

    def upsert_message_to_chat_by_id_and_message_id(_, message_id, message):
        history = chat.setdefault("history", {"messages": {}, "currentId": None})
        msgs = history.setdefault("messages", {})
        msgs[message_id] = {**msgs.get(message_id, {}), **message}
        history["currentId"] = message_id

    chats_mod = types.ModuleType("open_webui.models.chats")
    chats_mod.Chats = types.SimpleNamespace(
        get_chat_by_id=get_chat_by_id,
        get_message_by_id_and_message_id=get_message_by_id_and_message_id,
        upsert_message_to_chat_by_id_and_message_id=upsert_message_to_chat_by_id_and_message_id,
    )

    modules = {
        "open_webui": types.ModuleType("open_webui"),
        "open_webui.models": types.ModuleType("open_webui.models"),
        "open_webui.models.chats": chats_mod,
        "open_webui.utils": types.ModuleType("open_webui.utils"),
        "open_webui.utils.misc": types.ModuleType("open_webui.utils.misc"),
        "httpx": types.ModuleType("httpx"),
    }

    modules["open_webui.utils.misc"].deep_update = lambda d, u: {**d, **u}
    def _get_msg_list(msgs, mid):
        out = []
        curr = msgs.get(mid)
        while curr:
            out.insert(0, curr)
            mid = curr.get("parentId")
            curr = msgs.get(mid) if mid else None
        return out

    modules["open_webui.utils.misc"].get_message_list = _get_msg_list

    with patch.dict(sys.modules, modules):
        path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "openai_responses_api_pipeline.py"
        spec = spec_from_file_location("openai_responses_api_pipeline", path)
        pipeline = module_from_spec(spec)
        sys.modules[spec.name] = pipeline
        spec.loader.exec_module(pipeline)
        monkeypatch.setattr(pipeline, "Chats", chats_mod.Chats, raising=False)
        yield chat
