from importlib import import_module, reload


def _reload_pipeline():
    return reload(
        import_module("openwebui_devtoolkit.pipes.openai_responses_api_pipeline")
    )


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


def test_extract_instructions(dummy_chat):
    pipeline = _reload_pipeline()
    body = {
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "one"},
            {"role": "system", "content": "two"},
        ]
    }
    assert pipeline.Pipe._extract_instructions(body) == "two"


def test_apply_user_overrides_sets_log_level(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    class Dummy:
        def __init__(self, **vals):
            self._vals = vals

        def model_dump(self, exclude_none=True):  # mimic pydantic v2 API
            return self._vals

    overrides = Dummy(CUSTOM_LOG_LEVEL="DEBUG")
    pipe._apply_user_overrides(overrides)
    assert pipe.valves.CUSTOM_LOG_LEVEL == "DEBUG"
    import logging

    assert pipe.log.level == logging.DEBUG


def test_build_params_includes_reasoning(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()
    pipe.valves.REASON_EFFORT = "high"
    pipe.valves.REASON_SUMMARY = "concise"
    body = {"max_tokens": 50, "temperature": 0.4, "top_p": 0.9}
    params = pipe._build_params(body, "ins", [{"type": "function"}], "me@example.com")
    assert params["tool_choice"] == "auto"
    assert params["max_output_tokens"] == 50
    assert params["temperature"] == 0.4
    assert params["top_p"] == 0.9
    assert params["user"] == "me@example.com"
    assert params["reasoning"] == {"effort": "high", "summary": "concise"}


def test_update_usage_accumulates(dummy_chat):
    pipeline = _reload_pipeline()
    total = {}
    pipeline.Pipe._update_usage(total, {"input_tokens": 1, "output_tokens": 2, "pricing": {"total": 1}}, 1)
    pipeline.Pipe._update_usage(total, {"input_tokens": 4, "output_tokens": 3, "pricing": {"total": 2}}, 2)
    assert total == {
        "input_tokens": 5,
        "output_tokens": 5,
        "pricing": {"total": 3},
        "loops": 2,
    }


def test_to_obj_to_dict_roundtrip(dummy_chat):
    pipeline = _reload_pipeline()
    data = {"a": {"b": [1, {"c": 2}]}, "d": (3, 4)}
    obj = pipeline._to_obj(data)
    roundtrip = pipeline._to_dict(obj)
    assert roundtrip == data


def test_build_responses_payload_complex(dummy_chat):
    pipeline = _reload_pipeline()
    dummy_chat["history"] = {
        "currentId": "m2",
        "messages": {
            "m1": {
                "role": "user",
                "content": [{"text": "hi"}],
                "parentId": None,
                "files": [{"type": "image", "url": "img"}],
            },
            "m2": {
                "role": "assistant",
                "content": [{"text": "ok"}],
                "parentId": "m1",
                "sources": [{"_fc": [{"call_id": "c1", "name": "t", "arguments": "{}", "output": "42"}]}],
            },
        },
    }
    payload = pipeline.build_responses_payload("chat1")
    assert payload == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "hi"},
                {"type": "input_image", "image_url": "img"},
            ],
        },
        {"type": "function_call", "call_id": "c1", "name": "t", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "c1", "output": "42"},
        {"role": "assistant", "content": [{"type": "output_text", "text": "ok"}]},
    ]
