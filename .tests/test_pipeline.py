from importlib.util import spec_from_file_location, module_from_spec
import sys
from pathlib import Path
import types
from unittest.mock import AsyncMock, patch
import pytest


def _reload_pipeline():
    path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "openai_responses_api_pipeline.py"
    spec = spec_from_file_location("openai_responses_api_pipeline", path)
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


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
                "tool_calls": [
                    {"type": "function_call", "call_id": "c1", "name": "t", "arguments": "{}"}
                ],
                "tool_responses": [
                    {"type": "function_call_output", "call_id": "c1", "output": "42"}
                ],
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




@pytest.mark.asyncio
async def test_pipe_stream_loop(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    events = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r1")),
        types.SimpleNamespace(type="response.reasoning_summary_part.added"),
        types.SimpleNamespace(type="response.reasoning_summary_text.delta", delta="t"),
        types.SimpleNamespace(type="response.reasoning_summary_text.done", item_id="sum1", text="end"),
        types.SimpleNamespace(type="response.content_part.added"),
        types.SimpleNamespace(type="response.output_text.delta", delta="hi"),
        types.SimpleNamespace(type="response.output_text.done", text="hi"),
        types.SimpleNamespace(
            type="response.completed",
            response=types.SimpleNamespace(
                usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
            ),
        ),
    ]

    async def fake_stream(client, base_url, api_key, params):
        for e in events:
            yield e

    emitted: list[dict] = []

    async def emitter(evt: dict):
        emitted.append(evt)

    with patch.object(pipeline, "stream_responses", fake_stream), patch.object(
        pipe, "get_http_client", AsyncMock(return_value=object())
    ):
        gen = pipe.pipe(
            {},
            {},
            None,
            emitter,
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            {},
        )
        tokens = []
        async for chunk in gen:
            tokens.append(chunk)
    await pipe.on_shutdown()

    assert tokens == ["<think>", "t", "\n\n---\n\n", "</think>\n", "hi"]
    assert [e["data"] for e in emitted if e["type"] == "chat:completion"] == [
        {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3, "loops": 1}},
        {"done": True},
    ]
    assert emitted[-1]["type"] == "chat:completion"  # done event


@pytest.mark.asyncio
async def test_pipe_deletes_response(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    events = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="rX")),
        types.SimpleNamespace(type="response.output_text.delta", delta="ok"),
        types.SimpleNamespace(type="response.output_text.done", text="ok"),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]

    async def fake_stream(client, base_url, api_key, params):
        for e in events:
            yield e

    emitter = AsyncMock()

    with patch.object(pipeline, "stream_responses", fake_stream), patch.object(
        pipeline, "delete_response", AsyncMock()
    ) as del_mock, patch.object(pipe, "get_http_client", AsyncMock(return_value=object())):
        await pipe.pipe(
            {},
            {},
            None,
            emitter,
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            {},
        )
    await pipe.on_shutdown()

    del_mock.assert_awaited_once()
    args = del_mock.await_args.args
    assert args[1:] == (pipe.valves.BASE_URL, pipe.valves.API_KEY, "rX")


@pytest.mark.asyncio
async def test_debug_logs_citation_emitted(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    class Dummy:
        def __init__(self, **vals):
            self._vals = vals

        def model_dump(self, exclude_none=True):
            return self._vals

    user = {"valves": Dummy(CUSTOM_LOG_LEVEL="DEBUG")}

    events = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r1")),
        types.SimpleNamespace(type="response.output_text.delta", delta="ok"),
        types.SimpleNamespace(type="response.output_text.done", text="ok"),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]

    async def fake_stream(client, base_url, api_key, params):
        for e in events:
            yield e

    emitted = []

    async def emitter(evt: dict):
        emitted.append(evt)

    with patch.object(pipeline, "stream_responses", fake_stream), patch.object(
        pipe, "get_http_client", AsyncMock(return_value=object())
    ):
        await pipe.pipe(
            {},
            user,
            None,
            emitter,
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            {},
        )
    await pipe.on_shutdown()

    assert emitted[-1]["type"] == "citation"
    assert "Loop iteration" in emitted[-1]["data"]["document"][0]


@pytest.mark.asyncio
async def test_debug_logs_citation_saved_with_tool(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    class Dummy:
        def __init__(self, **vals):
            self._vals = vals

        def model_dump(self, exclude_none=True):
            return self._vals

    user = {"valves": Dummy(CUSTOM_LOG_LEVEL="DEBUG")}

    events = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r1")),
        types.SimpleNamespace(type="response.output_item.added", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.output_item.done", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]

    async def fake_stream(client, base_url, api_key, params):
        for e in events:
            yield e

    with patch.object(pipeline, "stream_responses", fake_stream), patch.object(
        pipe, "get_http_client", AsyncMock(return_value=object())
    ), patch.object(pipe, "_store_citation") as store_mock:
        await pipe.pipe(
            {},
            user,
            None,
            AsyncMock(),
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            {},
        )
    await pipe.on_shutdown()

    store_mock.assert_called_once()


@pytest.mark.asyncio
async def test_debug_logs_citation_multiple_turns(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    class Dummy:
        def __init__(self, **vals):
            self._vals = vals

        def model_dump(self, exclude_none=True):
            return self._vals

    user = {"valves": Dummy(CUSTOM_LOG_LEVEL="DEBUG")}

    events_first = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r1")),
        types.SimpleNamespace(type="response.output_item.added", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.output_item.done", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]
    events_second = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r2")),
        types.SimpleNamespace(type="response.output_text.delta", delta="ok"),
        types.SimpleNamespace(type="response.output_text.done", text="ok"),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]

    async def fake_stream1(*_a, **_kw):
        for e in events_first:
            yield e

    async def fake_stream2(*_a, **_kw):
        for e in events_second:
            yield e

    emitted = []

    async def emitter(evt: dict):
        emitted.append(evt)

    with patch.object(
        pipeline,
        "stream_responses",
        side_effect=[fake_stream1, fake_stream2],
    ), patch.object(pipe, "get_http_client", AsyncMock(return_value=object())):
        gen = pipe.pipe(
            {},
            user,
            None,
            emitter,
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            {"t": {"callable": AsyncMock(return_value="42")}},
        )
        async for _ in gen:
            pass
    await pipe.on_shutdown()

    assert emitted[-1]["type"] == "chat:completion"
    assert emitted[-1]["data"] == {"done": True}
    assert any(e["type"] == "citation" and e["data"]["source"]["name"] == "Debug Logs" for e in emitted)


@pytest.mark.asyncio
async def test_tool_metadata_persisted(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    events = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r1")),
        types.SimpleNamespace(type="response.output_item.added", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.output_item.done", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]

    async def fake_stream(client, base_url, api_key, params):
        for e in events:
            yield e

    tools = {"t": {"callable": AsyncMock(return_value="42")}}
    updates = []

    def upsert(chat_id, message_id, data):
        updates.append(data)

    with patch.object(pipeline, "stream_responses", fake_stream), patch.object(
        pipe, "get_http_client", AsyncMock(return_value=object())
    ), patch.object(
        pipeline.Chats,
        "upsert_message_to_chat_by_id_and_message_id",
        side_effect=upsert,
    ):
        await pipe.pipe(
            {},
            {},
            None,
            AsyncMock(),
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            tools,
        )
    await pipe.on_shutdown()

    assert any("tool_calls" in u for u in updates)
    assert updates[-1]["tool_calls"][0]["name"] == "t"
    assert updates[-1]["tool_responses"][0]["output"] == "42"


@pytest.mark.asyncio
async def test_previous_response_cleanup(dummy_chat):
    pipeline = _reload_pipeline()
    pipe = pipeline.Pipe()

    events_first = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r1")),
        types.SimpleNamespace(type="response.output_item.added", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.output_item.done", item=types.SimpleNamespace(type="function_call", name="t", call_id="c1", arguments="{}")),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]
    events_second = [
        types.SimpleNamespace(type="response.created", response=types.SimpleNamespace(id="r2")),
        types.SimpleNamespace(type="response.output_text.delta", delta="ok"),
        types.SimpleNamespace(type="response.output_text.done", text="ok"),
        types.SimpleNamespace(type="response.completed", response=types.SimpleNamespace(usage={})),
    ]

    async def fake_stream1(*_args, **_kwargs):
        for e in events_first:
            yield e

    async def fake_stream2(*_args, **_kwargs):
        for e in events_second:
            yield e

    with patch.object(
        pipeline,
        "stream_responses",
        side_effect=[fake_stream1, fake_stream2],
    ), patch.object(
        pipeline,
        "delete_response",
        AsyncMock(),
    ) as del_mock, patch.object(
        pipe,
        "get_http_client",
        AsyncMock(return_value=object()),
    ):
        await pipe.pipe(
            {},
            {},
            None,
            AsyncMock(),
            AsyncMock(),
            [],
            {"chat_id": "chat1", "message_id": "m1", "function_calling": "native"},
            {"t": {"callable": AsyncMock(return_value="42")}},
        )
    await pipe.on_shutdown()

    assert del_mock.await_count == 2
    ids = [c.args[3] for c in del_mock.await_args_list]
    assert ids == ["r1", "r2"]

