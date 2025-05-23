import sys
import types
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

import pytest


def _load_pipe(title_store):
    mods = {
        "open_webui": types.ModuleType("open_webui"),
        "open_webui.models": types.ModuleType("open_webui.models"),
        "open_webui.models.chats": types.ModuleType("open_webui.models.chats"),
    }

    mods["open_webui.models.chats"].Chats = types.SimpleNamespace(
        update_chat_title_by_id=lambda cid, t: title_store.__setitem__(cid, t),
        get_chat_title_by_id=lambda cid: title_store.get(cid),
    )

    with pytest.MonkeyPatch.context() as m:
        m.context()
        for name, mod in mods.items():
            m.setitem(sys.modules, name, mod)
        path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "dynamic_title_update_demo.py"
        spec = spec_from_file_location("dynamic_title_update_demo", path)
        pipe_mod = module_from_spec(spec)
        sys.modules[spec.name] = pipe_mod
        spec.loader.exec_module(pipe_mod)
        return pipe_mod


@pytest.mark.asyncio
async def test_dynamic_title_updates():
    titles = {}
    mod = _load_pipe(titles)
    pipe = mod.Pipe()

    body = {"messages": [{"role": "user", "content": "hello"}]}
    metadata = {"chat_id": "c1"}
    request = types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace(config=types.SimpleNamespace(ENABLE_TITLE_GENERATION=True))))

    async for _ in pipe.pipe(body, metadata, request):
        pass

    assert titles["c1"].startswith("Completed")
    assert request.app.state.config.ENABLE_TITLE_GENERATION is True
