from importlib import import_module, reload
def _reload_pipeline():
    return reload(import_module("openwebui_devtoolkit.pipes.openai_responses_api_pipeline"))


def test_prepare_tools_variants(dummy_chat):
    pipeline = _reload_pipeline()
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
    tools = pipeline.prepare_tools(reg)
    assert tools[0]["name"] == "foo"
    assert tools[1]["name"] == "bar"
    assert tools[0]["type"] == "function"
    assert tools[1]["type"] == "function"


def test_build_responses_payload(dummy_chat):
    pipeline = _reload_pipeline()
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

    payload = pipeline.build_responses_payload("chat1")
    assert payload == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "hello"}]},
    ]


def test_pretty_log_block(dummy_chat):
    pipeline = _reload_pipeline()
    out = pipeline.pretty_log_block({"a": 1}, label="lbl")
    assert "lbl =" in out
    assert '{\n  "a": 1\n}' in out
