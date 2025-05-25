import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

def _load_pipe():
    path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "example_metadata_persistence.py"
    spec = spec_from_file_location("example_metadata_persistence", path)
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.Pipe


@pytest.mark.asyncio
async def test_custom_metadata_persists_across_turns(dummy_chat):
    Pipe = _load_pipe()
    pipe = Pipe()
    from open_webui.models.chats import Chats
    chat_id = "chat1"

    # First turn
    body1 = {"messages": [{"id": "u1", "role": "user", "content": "hi"}]}
    metadata1 = {"chat_id": chat_id, "message_id": "m1"}
    out1 = [chunk async for chunk in pipe.pipe(body1, metadata1)]
    assert out1 == ["No previous meta\n", "Echo: hi"]
    msg1 = Chats.get_message_by_id_and_message_id(chat_id, "m1")
    assert msg1["custom_meta"] == "stored:hi"
    # Simulate final content save
    Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, "m1", {"content": "Echo: hi"})

    # Second turn
    body2 = {
        "messages": [
            {"id": "u1", "role": "user", "content": "hi"},
            {"id": "m1", "role": "assistant", "content": "Echo: hi"},
            {"id": "u2", "role": "user", "content": "again"},
        ]
    }
    metadata2 = {"chat_id": chat_id, "message_id": "m2"}
    out2 = [chunk async for chunk in pipe.pipe(body2, metadata2)]
    assert out2[0] == "Previous meta: stored:hi\n"
    msg2 = Chats.get_message_by_id_and_message_id(chat_id, "m2")
    assert msg2["custom_meta"] == "stored:again"
