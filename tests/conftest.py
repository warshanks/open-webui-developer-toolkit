import sys
import types
import pytest


@pytest.fixture(autouse=True)
def stub_open_webui(monkeypatch):
    """Provide a minimal stub of the ``open_webui.models.chats`` module."""
    dummy_chat = {"history": {"currentId": None, "messages": {}}}

    def get_chat_by_id(_):
        return types.SimpleNamespace(chat=dummy_chat)

    chats_mod = types.ModuleType("open_webui.models.chats")
    chats_mod.Chats = types.SimpleNamespace(get_chat_by_id=get_chat_by_id)

    monkeypatch.setitem(sys.modules, "open_webui", types.ModuleType("open_webui"))
    monkeypatch.setitem(sys.modules, "open_webui.models", types.ModuleType("open_webui.models"))
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", chats_mod)

    yield dummy_chat
