from importlib.util import module_from_spec, spec_from_file_location
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


# Helper to load the pipeline module fresh for each test

def _load_pipeline():
    path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "openai_responses_api_pipeline.py"
    spec = spec_from_file_location("openai_responses_api_pipeline", path)
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_transform_tools_for_responses_api(dummy_chat):
    pipeline = _load_pipeline()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calc",
                "parameters": {"type": "object"},
            },
        },
        {"type": "web_search", "web_search": {"search_context_size": "medium"}},
    ]
    out = pipeline.transform_tools_for_responses_api(tools)
    assert out == [
        {"type": "function", "name": "calc", "parameters": {"type": "object"}},
        {"type": "web_search", "search_context_size": "medium"},
    ]


@pytest.mark.asyncio
async def test_build_chat_history_for_responses_api(dummy_chat):
    pipeline = _load_pipeline()
    dummy_chat["history"] = {
        "currentId": "m2",
        "messages": {
            "m1": {"role": "user", "content": [{"text": "hi"}], "parentId": None},
            "m2": {"role": "assistant", "content": [{"text": "hello"}], "parentId": "m1"},
        },
    }

    history = await pipeline.build_chat_history_for_responses_api(chat_id="chat1")
    assert history == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "hello"}]},
    ]


@pytest.mark.asyncio
async def test_prepare_payload_includes_reasoning(dummy_chat):
    pipeline = _load_pipeline()
    pipe = pipeline.Pipe()
    pipe.valves.REASON_SUMMARY = "concise"
    body = {"model": "openai_responses.o3", "reasoning_effort": "high"}
    params = await pipeline.prepare_payload(
        pipe.valves,
        body,
        "ins",
        [],
        "user@example.com",
        chat_id="chat1",
    )
    assert params["model"] == "o3"
    assert params["reasoning"] == {"effort": "high", "summary": "concise"}


def test_parse_responses_sse(dummy_chat):
    pipeline = _load_pipeline()
    raw = json.dumps({"delta": "hi"})
    evt = pipeline.parse_responses_sse("response.output_text.delta", raw)
    assert evt == {"delta": "hi", "type": "response.output_text.delta"}


@pytest.mark.asyncio
async def test_execute_responses_tool_calls(dummy_chat):
    pipeline = _load_pipeline()

    async def tool(x):
        return x + 1

    call = SimpleNamespace(name="t", arguments="{\"x\": 1}")
    results = await pipeline.execute_responses_tool_calls(
        [call],
        {"t": {"callable": tool}},
    )
    assert results == [2]
