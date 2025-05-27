import json
import sys
import types
from types import SimpleNamespace
from datetime import datetime

# Provide a minimal orjson stub when the real library isn't installed
if "orjson" not in sys.modules:
    orjson_stub = types.SimpleNamespace(
        loads=lambda b: json.loads(b),
        dumps=lambda obj: json.dumps(obj).encode(),
    )
    sys.modules["orjson"] = orjson_stub

import httpx
import pytest

from functions.pipes.openai_responses_pipeline import (
    Pipe,
    delete_response,
    execute_responses_tool_calls,
    simplify_user_agent,
    transform_tools_for_responses_api,
)


def test_simplify_user_agent() -> None:
    chrome = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )
    assert simplify_user_agent(chrome) == "Chrome 123"
    assert simplify_user_agent("") == "Unknown"
    assert simplify_user_agent("FooBar/1.0") == "FooBar/1.0".split()[0]


def test_transform_tools_for_responses_api() -> None:
    tools = [
        {"type": "function", "function": {"name": "hello"}},
        {"type": "web_search", "web_search": {"search_context_size": "high"}},
        {"type": "noop"},
        {"other": 1},
    ]
    out = transform_tools_for_responses_api(tools)
    assert out[0] == {"type": "function", "name": "hello"}
    assert out[1] == {"type": "web_search", "search_context_size": "high"}
    assert out[2] == {"type": "noop"}
    assert out[3] == {"other": 1}

    assert transform_tools_for_responses_api(None) == []
    assert transform_tools_for_responses_api([1, {"type": "noop"}]) == [{"type": "noop"}]


def test_update_usage() -> None:
    pipe = Pipe()
    total: dict[str, int] = {}
    pipe._update_usage(total, {"input_tokens": 5}, 1)
    assert total == {"input_tokens": 5, "loops": 1}
    pipe._update_usage(total, {"input_tokens": 3, "details": {"a": 1}}, 2)
    assert total["input_tokens"] == 8
    assert total["details"] == {"a": 1}
    assert total["loops"] == 2


@pytest.mark.asyncio
async def test_execute_responses_tool_calls() -> None:
    async def a_tool(x: int) -> int:
        return x * 2

    def b_tool(y: int) -> int:
        return y + 1

    registry = {
        "a": {"callable": a_tool},
        "b": {"callable": b_tool},
    }
    calls = [
        SimpleNamespace(name="a", arguments=json.dumps({"x": 2})),
        SimpleNamespace(name="b", arguments=json.dumps({"y": 3})),
        SimpleNamespace(name="missing", arguments="{}"),
    ]
    result = await execute_responses_tool_calls(calls, registry)
    assert result == [4, 4, "Tool not found"]


@pytest.mark.asyncio
async def test_stream_responses() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api/responses")
        assert request.headers["Authorization"] == "Bearer KEY"
        content = (
            b"event: delta\n"
            b'data: {"type": "delta", "foo": 1}\n\n'
            b"data: [DONE]\n\n"
        )
        return httpx.Response(200, content=content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pipe = Pipe()
    valves = pipe.valves.model_copy(update={"BASE_URL": "https://api", "API_KEY": "KEY"})
    events = [
        event async for event in pipe._stream_responses(valves, client, {"model": "gpt"})
    ]
    await client.aclose()
    assert events == [{"type": "delta", "foo": 1}]


@pytest.mark.asyncio
async def test_stream_responses_ignores_comments() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        content = (
            b": comment\n\n"
            b"data: {\"bar\": 2}\n\n"
            b"data: [DONE]\n\n"
        )
        return httpx.Response(200, content=content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pipe = Pipe()
    valves = pipe.valves.model_copy(update={"BASE_URL": "https://api", "API_KEY": "KEY"})
    events = [
        event async for event in pipe._stream_responses(valves, client, {"model": "gpt"})
    ]
    await client.aclose()
    assert events == [{"bar": 2}]


def test_info_suffix_helpers() -> None:
    pipe = Pipe()
    user = {"name": "Jane", "email": "jane@example.com"}
    assert pipe._get_user_info_suffix(user) == "user_info: Jane <jane@example.com>"

    request = types.SimpleNamespace(
        headers={
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Linux"',
            "user-agent": "Mozilla/5.0 Chrome/123.0 Safari/537.36",
        }
    )
    expected = "browser_info: Mobile | Linux | Browser: Chrome 123"
    assert pipe._get_browser_info_suffix(request) == expected


@pytest.mark.asyncio
async def test_build_chat_history_for_responses_api() -> None:
    pipe = Pipe()
    messages = [
        {"role": "system", "content": "skip"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": [{"type": "image", "url": "http://img"}]},
    ]
    history = await pipe._build_chat_history_for_responses_api(None, messages)
    assert history == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "hello"}]},
        {"role": "user", "content": [{"type": "input_image", "image_url": "http://img"}]},
    ]


@pytest.mark.asyncio
async def test_delete_response() -> None:
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        assert request.method == "DELETE"
        assert request.url == httpx.URL("https://api/responses/123")
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await delete_response(client, "https://api", "KEY", "123")
    await client.aclose()
    assert called


@pytest.mark.asyncio
async def test_emit_status() -> None:
    pipe = Pipe()
    events: list[dict] = []

    async def emitter(event: dict) -> None:
        events.append(event)

    last_status = [None]
    await pipe._emit_status(emitter, "start", last_status)
    # Duplicate status should not emit
    await pipe._emit_status(emitter, "start", last_status)
    await pipe._emit_status(emitter, "done", last_status, done=True)
    assert events == [
        {"type": "status", "data": {"description": "start", "done": False}},
        {"type": "status", "data": {"description": "done", "done": True}},
    ]


@pytest.mark.asyncio
async def test_prepare_request_body_injection(monkeypatch) -> None:
    pipe = Pipe()
    valves = pipe.valves.model_copy(
        update={
            "INJECT_CURRENT_DATE": True,
            "INJECT_USER_INFO": True,
            "INJECT_BROWSER_INFO": True,
            "BASE_URL": "https://api",
            "API_KEY": "KEY",
        }
    )

    async def fake_history(*_args, **_kwargs):
        return [
            {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
        ]

    monkeypatch.setattr(pipe, "_build_chat_history_for_responses_api", fake_history)

    class FakeDateTime:
        @staticmethod
        def now():
            return datetime(2000, 1, 1)

        @staticmethod
        def strftime(fmt: str) -> str:  # pragma: no cover - unused
            return ""

    monkeypatch.setattr(
        "functions.pipes.openai_responses_pipeline.datetime",
        FakeDateTime,
    )

    body = {
        "model": "o3-mini-high",
        "messages": [{"role": "system", "content": "sys"}],
        "tools": [{"type": "function", "function": {"name": "hello"}}],
    }

    request = types.SimpleNamespace(
        headers={
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "user-agent": "Mozilla/5.0 Chrome/123 Safari/537.36",
        }
    )

    user = {"name": "Jane", "email": "jane@example.com"}

    result = await pipe._prepare_request_body(valves, body, None, user, request)
    assert result["model"] == "o3-mini"
    assert "Today's date:" in result["instructions"]
    assert "browser_info:" in result["instructions"]
    assert result["user"] == "jane@example.com"
    assert result["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
    ]
    # reasoning effort inferred from model alias
    assert result["reasoning"]["effort"] == "high"
