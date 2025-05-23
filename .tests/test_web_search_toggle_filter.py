from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys
import asyncio
import pytest


def _load_filter():
    path = Path(__file__).resolve().parents[1] / "functions" / "filters" / "web_search_toggle_filter.py"
    spec = spec_from_file_location("web_search_toggle_filter", path)
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_add_tool_for_supported_models():
    mod = _load_filter()
    flt = mod.Filter()
    body = {"model": "openai_responses.gpt-4o"}
    out = await flt.inlet(body)
    assert any(t.get("type") == "web_search" for t in out.get("tools", []))


@pytest.mark.asyncio
async def test_no_duplicate_tools():
    mod = _load_filter()
    flt = mod.Filter()
    body = {
        "model": "openai_responses.gpt-4.1-mini",
        "tools": [{"type": "web_search", "search_context_size": "medium"}],
    }
    out = await flt.inlet(body)
    assert len([t for t in out["tools"] if t.get("type") == "web_search"]) == 1


@pytest.mark.asyncio
async def test_search_preview_for_other_models():
    mod = _load_filter()
    flt = mod.Filter()
    body = {"model": "other"}
    out = await flt.inlet(body)
    assert out["model"] == "gpt-4o-search-preview"
    assert any(t.get("type") == "web_search" for t in out.get("tools", []))


def test_outlet_handles_missing_emitter():
    mod = _load_filter()
    flt = mod.Filter()
    body = {
        "model": "other",
        "messages": [
            {"role": "assistant", "content": "see https://ex.com/?utm_source=openai"}
        ],
    }

    out = asyncio.run(flt.outlet(body, __event_emitter__=None))
    assert out is body


def test_outlet_returns_body_for_supported_model():
    mod = _load_filter()
    flt = mod.Filter()
    body = {"model": "openai_responses.gpt-4o"}

    out = asyncio.run(flt.outlet(body, __event_emitter__=None))
    assert out is body


