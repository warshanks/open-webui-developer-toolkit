import json
import types
from types import SimpleNamespace

import logging

import httpx
import pytest

from functions.pipes.openai_responses_api_pipeline import (
    Pipe,
    execute_responses_tool_calls,
    parse_responses_sse,
    sanitize_for_log,
    simplify_user_agent,
    stream_responses,
    transform_tools_for_responses_api,
)


def test_sanitize_for_log():
    data = {
        "profile_image_url": "http://example.com/pic.png",
        "files": [
            {
                "id": "1",
                "name": "orig.txt",
                "size": 10,
                "file": {"filename": "ignored.txt", "meta": {"size": 20}},
            }
        ],
        "data": {"content": "secret"},
        "nested": [{"profile_image_url": "foo"}],
    }
    out = sanitize_for_log(data)
    assert out["profile_image_url"] == "<profile_image_url>"
    assert out["files"] == [{"id": "1", "name": "orig.txt", "size": 10}]
    assert out["data"] == {"content": "<content>"}
    assert out["nested"][0]["profile_image_url"] == "<profile_image_url>"


def test_simplify_user_agent():
    chrome = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )
    assert simplify_user_agent(chrome) == "Chrome 123"
    assert simplify_user_agent("") == "Unknown"
    assert simplify_user_agent("FooBar/1.0") == "FooBar/1.0".split()[0]


def test_parse_responses_sse():
    data = json.dumps({"foo": 1})
    result = parse_responses_sse("delta", data)
    assert result == {"foo": 1, "type": "delta"}

    result = parse_responses_sse("delta", json.dumps({"type": "other"}))
    assert result == {"type": "other"}

    result = parse_responses_sse(None, json.dumps({"bar": 2}))
    assert result == {"bar": 2, "type": "message"}


def test_transform_tools_for_responses_api():
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


def test_update_usage():
    pipe = Pipe()
    total: dict[str, int] = {}
    pipe._update_usage(total, {"input_tokens": 5}, 1)
    assert total == {"input_tokens": 5, "loops": 1}
    pipe._update_usage(total, {"input_tokens": 3, "details": {"a": 1}}, 2)
    assert total["input_tokens"] == 8
    assert total["details"] == {"a": 1}
    assert total["loops"] == 2


@pytest.mark.asyncio
async def test_execute_responses_tool_calls():
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
async def test_stream_responses():
    async def handler(request: httpx.Request) -> httpx.Response:
        content = (
            b"event: delta\n"
            b'data: {"foo": 1}\n\n'
            b"data: [DONE]\n\n"
        )
        return httpx.Response(200, content=content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gen = stream_responses(client, "https://api", "KEY", {"model": "gpt"})
    events = [event async for event in gen]
    await client.aclose()
    assert events == [{"foo": 1, "type": "delta"}]


def test_info_suffix_helpers():
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


def test_user_valve_log_level_override():
    pipe = Pipe()
    assert pipe.log.level == logging.INFO

    valves = Pipe.UserValves(CUSTOM_LOG_LEVEL="DEBUG")
    pipe._apply_user_valve_overrides(valves)

    assert pipe.log.level == logging.DEBUG
    handler, _ = pipe._attach_debug_handler()
    assert handler is not None
    pipe._detach_debug_handler(handler)
