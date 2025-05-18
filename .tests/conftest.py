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

    chats_mod = types.ModuleType("open_webui.models.chats")
    chats_mod.Chats = types.SimpleNamespace(get_chat_by_id=get_chat_by_id)

    modules = {
        "open_webui": types.ModuleType("open_webui"),
        "open_webui.models": types.ModuleType("open_webui.models"),
        "open_webui.models.chats": chats_mod,
        "httpx": types.ModuleType("httpx"),
    }

    with patch.dict(sys.modules, modules):
        path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "openai_responses_api_pipeline.py"
        spec = spec_from_file_location("openai_responses_api_pipeline", path)
        pipeline = module_from_spec(spec)
        sys.modules[spec.name] = pipeline
        spec.loader.exec_module(pipeline)
        monkeypatch.setattr(pipeline, "Chats", chats_mod.Chats, raising=False)
        yield chat
