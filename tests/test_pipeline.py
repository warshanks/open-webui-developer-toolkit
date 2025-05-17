import sys
import types

sys.modules.setdefault("httpx", types.ModuleType("httpx"))
_dummy_mod = types.ModuleType("open_webui.models.chats")
_dummy_mod.Chats = types.SimpleNamespace(get_chat_by_id=lambda _ : None)
sys.modules.setdefault("open_webui", types.ModuleType("open_webui"))
sys.modules.setdefault("open_webui.models", types.ModuleType("open_webui.models"))
sys.modules.setdefault("open_webui.models.chats", _dummy_mod)

from openwebui_devtoolkit.pipes.openai_responses_api_pipeline import (  # noqa: E402
    build_responses_payload,
    prepare_tools,
    pretty_log_block,
)


def test_prepare_tools_variants(dummy_chat):
    reg = {
        "tools": {
            "one": {
                "spec": {
                    "name": "foo",
                    "description": "d",
                    "parameters": {"type": "object"},
                }
            },
            "two": {"spec": {"function": {"name": "bar"}}},
        }
    }
    tools = prepare_tools(reg)
    assert tools[0]["name"] == "foo"
    assert tools[1]["name"] == "bar"
    assert tools[0]["type"] == "function"
    assert tools[1]["type"] == "function"


def test_build_responses_payload(dummy_chat):
    dummy_chat["history"] = {
        "currentId": "m2",
        "messages": {
            "m1": {"role": "user", "content": [{"text": "hi"}], "parentId": None},
            "m2": {
                "role": "assistant",
                "content": [{"text": "hello"}],
                "parentId": "m1",
            },
        },
    }

    payload = build_responses_payload("chat1")
    assert payload == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "hello"}]},
    ]


def test_pretty_log_block():
    out = pretty_log_block({"a": 1}, label="lbl")
    assert "lbl =" in out
    assert '{\n  "a": 1\n}' in out
