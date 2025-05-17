"""
title: OpenAI Responses API Pipeline
id: openai_responses_api_pipeline
author: Justin Kropp
author_url: https://github.com/jrkropp
description: Brings OpenAI Response API support to Open WebUI, enabling features not possible via Completions API.
version: 1.6.10
license: MIT
requirements: httpx

------------------------------------------------------------------------------
📌 OVERVIEW
------------------------------------------------------------------------------
This pipeline brings OpenAI Responses API with Open WebUI, enabling features not possible via Completions API.

Key Features:
   1) Supports o3/o4-mini reasoning models (including visible <think> reasoning summaries)
   2) Image input support (output support coming soon...)
   3) Optional built-in web search tool (powered by OpenAI web_search tool)
   4) Usage stats passthrough (to OpenWebUI GUI)
   5) Supports cache pricing (up to 75% discount for input tokens that hit OpenAI Cache)
   6) Support LiteLLM and other Response API compatible gateways.
   7) Optimized native tool calling:
        - True parallel tool calling support (i.e., gather multiple tool calls within a single turn and execute in parallel)
        - Status emitters show which tool(s) the model is calling
        - Tool results are emitted as citations for traceability & transparancy.
        - Tool results are retained in conversation history (function_call/function_call_output) so users can ask follow up questions
        - Retain reasoning tokens across tool turns (loops).
            o3/o4-mini internal reasoning tokens aren't externally visible and therefore can't be passed back into the model.
            To work around this, the pipe temporarily uses previous_response_id to retain context within tool turn loops.
            This allows reasoning models to call turns mid-reasoning, get tool result and continue reasoning.
            This is ONLY possible with the responses API and sigificantly improves speed, reduces cost (since model doesn't need
            to re-reasoning) and improved ability.

Future Improvements:
   TODO - Image output support
   TODO - Document input support (e.g., PDFs, other files via __files__ parameter in pipe() function).
   TODO - Consider adding support for file_search (built-in OpenAI tool)

Notes:
   - This pipeline is experimental. USE AT YOUR OWN RISK.
   - Duplicate/clone this pipeline if you want multiple models.
   - Tool calling requires 'OpenWebUI Model Advanced Params → Function Calling → set to "Native"'

Read more about OpenAI Responses API:
- https://openai.com/index/new-tools-for-building-agents/
- https://platform.openai.com/docs/quickstart?api-mode=responses
- https://platform.openai.com/docs/api-reference/responses

-----------------------------------------------------------------------------
🛠
-----------------------------------------------------------------------------
• 1.6.10 (2025-05-16)
    - Switched streaming implementation to use plain HTTP via httpx
    - Dropped the OpenAI SDK dependency
    - Added lightweight SSE parser for Responses API events
• 1.6.9 (2025-05-12)
    - Updated requirements to "openai>=1.78.0" (library will automatically install when pipe in initialized).
    - Added UserValves class to allow users to override system valve settings.
    - Improved logging
• 1.6.8 (2025-05-09)
    - Improved logging formating and control. Replaced DEBUG (on/off) valve with more granular CUSTOM_LOG_LEVEL (DEBUG/INFO/WARNING/ERROR).
    - Refactored code for improved readability and maintainability.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime
from types import SimpleNamespace
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Literal

import httpx
from fastapi import Request
from open_webui.models.chats import Chats
from pydantic import BaseModel, Field

EMOJI_LEVELS = {
    logging.DEBUG: "\U0001F50D",
    logging.INFO: "\u2139",
    logging.WARNING: "\u26A0",
    logging.ERROR: "\u274C",
    logging.CRITICAL: "\U0001F525",
}


class Pipe:
    """Pipeline to interact with the OpenAI Responses API."""
    class Valves(BaseModel):
        BASE_URL: str = Field(
            default="https://api.openai.com/v1",
            description=(
                "The base URL to use with the OpenAI SDK. Defaults to the official "
                "OpenAI API endpoint. Supports LiteLLM and other custom endpoints."
            ),
        )

        API_KEY: str = Field(
            default=os.getenv("OPENAI_API_KEY", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
            description="Your OpenAI API key. Defaults to the value of the OPENAI_API_KEY environment variable. ",
        )

        MODEL_ID: str = Field(
            default="gpt-4.1",
            description=(
                "Model ID used to generate responses. Defaults to 'gpt-4.1'. Note: The model ID must be a valid OpenAI model ID. E.g. 'gpt-4o', 'o3', etc."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-model

        REASON_SUMMARY: Literal["auto", "concise", "detailed", None] = Field(
            default=None,
            description=(
                "Reasoning summary style for o-series models (if your OpenAI org has access). OpenAI may require identify verification before enabling. Leave blank to disable (default)."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning

        REASON_EFFORT: Literal["low", "medium", "high", None] = Field(
            default=None,
            description=(
                "Reasoning effort level for o-series models. "
                "Leave blank to disable (default)."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning

        ENABLE_WEB_SEARCH: bool = Field(
            default=False,
            description=(
                "Whether to enable OpenAI's built-in 'web_search' tool. If True, adds {'type': 'web_search'} to tools (unless already present). Note: Tool occurs additional charge each time the model calls it"
            ),
        )  # Read more: https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses

        SEARCH_CONTEXT_SIZE: Literal["low", "medium", "high", None] = Field(
            default="medium",
            description=(
                "Specifies the OpenAI web search context size: low | medium | high. Default is 'medium'. Affects cost, quality, and latency. Only used if ENABLE_WEB_SEARCH=True."
            ),
        )

        PARALLEL_TOOL_CALLS: bool = Field(
            default=True,
            description="Whether tool calls can be parallelized. Defaults to True if not set.",
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-parallel_tool_calls

        # TODO Need to rename as it's not truely max tool calls.  It's max tool loops.  It can call an unlimited number of tools within a single loop.
        MAX_TOOL_CALLS: int = Field(
            default=5,
            description=(
                "Maximum number of tool calls the model can make in a single request. This is a hard stop safety limit to prevent infinite loops. Defaults to 5."
            ),
        )

        STORE_RESPONSE: bool = Field(
            default=False,
            description=(
                "Whether to store the generated model response (on OpenAI's side) for later debuging. Defaults to False."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-store

        CUSTOM_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
            default=os.getenv("GLOBAL_LOG_LEVEL", "INFO").upper(),
            description="Select logging level.",
        )

    class UserValves(BaseModel):
        CUSTOM_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "INHERIT"] = "INHERIT"

    def __init__(self) -> None:
        """Initialize the pipeline and logging."""
        self.valves = self.Valves()
        self.name = f"OpenAI: {self.valves.MODEL_ID}"  # TODO fix this as MODEL_ID value can't be accessed from within __init__.
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

        self.log = logging.getLogger(self.name)
        self.log.propagate = False
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(emo)s %(levelname)-8s | %(name)-20s:%(lineno)-4d — %(message)s"))
        handler.addFilter(lambda r: setattr(r, "emo", EMOJI_LEVELS.get(r.levelno, "\u2753")) or True)
        self.log.handlers = [handler]
        self.log.setLevel(logging.INFO)

    async def on_shutdown(self) -> None:
        """Clean up the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Dict[str, Any],
        __request__: Request,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __event_call__: Callable[[dict[str, Any]], Awaitable[Any]],  # unused
        __files__: list[dict[str, Any]],
        __metadata__: dict[str, Any],
        __tools__: dict[str, Any],
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Stream responses from OpenAI and handle tool calls."""
        start_ns = time.perf_counter_ns()
        self._apply_user_overrides(__user__.get("valves"))

        if __tools__ and __metadata__.get("function_calling") != "native":
            yield (
                "🛑 Tools detected, but native function calling is disabled.\n\n"
                "To enable tools in this chat, switch Function Calling to 'Native'."
            )
            self.log.error("Tools present but native function calling disabled")
            return

        self.log.info(
            'CHAT_MSG pipe="%s" model=%s user=%s chat=%s message=%s',
            self.name,
            self.valves.MODEL_ID,
            __user__.get("email", "anon"),
            __metadata__["chat_id"],
            __metadata__["message_id"],
        )

        client = await self.get_http_client()
        chat_id = __metadata__["chat_id"]
        input_messages = build_responses_payload(chat_id)
        # TODO Consider setting the user system prompt (if specified) as a developer message rather than replacing the model system prompt.  Right now it get's the last instance of system message (user system prompt takes precidence)
        instructions = self._extract_instructions(body)

        tools = prepare_tools(__tools__)
        if self.valves.ENABLE_WEB_SEARCH:
            tools.append(
                {
                    "type": "web_search",
                    "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,
                }
            )

        self.log.debug(pretty_log_block(tools, "tools"))
        self.log.debug(pretty_log_block(instructions, "instructions"))
        self.log.debug(pretty_log_block(input_messages, "input_messages"))

        request_params = self._build_params(
            body, instructions, tools, __user__.get("email")
        )
        usage_total: dict[str, Any] = {}
        last_response_id = None
        temp_input: list[dict[str, Any]] = []
        is_model_thinking = False

        for loop_count in range(1, self.valves.MAX_TOOL_CALLS + 1):
            self.log.debug("Loop iteration #%d", loop_count)
            if loop_count == 1:
                request_params.update({"input": input_messages})
            else:
                request_params.update(
                    {
                        "previous_response_id": last_response_id,
                        "input": temp_input,
                    }
                )
                temp_input = []

            try:
                pending_calls: list[SimpleNamespace] = []
                self.log.debug("response_stream created for loop #%d", loop_count)
                async for event in stream_responses(
                    client, self.valves.BASE_URL, self.valves.API_KEY, request_params
                ):
                    et = event.type
                    self.log.debug("Event received: %s", et)

                    if et == "response.created":
                        last_response_id = event.response.id
                        continue
                    if et in {"response.done", "response.failed", "response.incomplete", "error"}:
                        self.log.error("Stream ended with event: %s", et)
                        break
                    if et == "response.reasoning_summary_part.added":
                        if not is_model_thinking:
                            is_model_thinking = True
                            yield "<think>"
                        continue
                    if et == "response.reasoning_summary_text.delta":
                        yield event.delta
                        continue
                    if et == "response.reasoning_summary_text.done":
                        yield "\n\n---\n\n"
                        request_params["input"].append(
                            {
                                "type": "reasoning",
                                "id": event.item_id,
                                "summary": [
                                    {"type": "summary_text", "text": event.text}
                                ],
                            }
                        )
                        continue
                    if et == "response.content_part.added":
                        if is_model_thinking:
                            is_model_thinking = False
                            yield "</think>\n"
                        continue
                    if et == "response.output_text.delta":
                        yield event.delta
                        continue
                    if et == "response.output_text.done":
                        # TODO is this still needed now that I retain message context using previous_response_id?
                        request_params["input"].append(
                            {
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": event.text}],
                            }
                        )
                        continue
                    if et == "response.output_item.added":
                        item = getattr(event, "item", None)
                        if getattr(item, "type", None) == "function_call":
                            await __event_emitter__({"type": "status", "data": {"description": f"🔧 Running {item.name}...", "done": False}})
                        elif getattr(item, "type", None) == "web_search_call":
                            await __event_emitter__({"type": "status", "data": {"description": "🔍 Searching the internet...", "done": False}})
                        continue
                    if et == "response.output_item.done":
                        item = getattr(event, "item", None)
                        if getattr(item, "type", None) == "function_call":
                            pending_calls.append(item)
                            # TODO consider removing this.  It can look strange where there are back to back calls and it rapidly flashes and clears.
                            await __event_emitter__({"type": "status", "data": {"description": "", "done": True}})
                        elif getattr(item, "type", None) == "web_search_call":
                            await __event_emitter__({"type": "status", "data": {"description": "", "done": True}})
                        continue
                    if et == "response.output_text.annotation.added":
                        raw = str(getattr(event, "annotation", ""))
                        title_m = re.search(r"title='([^']*)'", raw)
                        url_m = re.search(r"url='([^']*)'", raw)
                        title = title_m.group(1) if title_m else "Unknown Title"
                        url = url_m.group(1) if url_m else ""
                        url = url.replace("?utm_source=openai", "").replace("&utm_source=openai", "")
                        await __event_emitter__({"type": "citation", "data": {"document": [title], "metadata": [{"date_accessed": datetime.now().isoformat(), "source": title}], "source": {"name": url, "url": url}}})
                        continue
                    if et == "response.completed" and event.response.usage:
                        self._update_usage(usage_total, event.response.usage, loop_count)
                        yield {"usage": usage_total}
                        continue
            except Exception as ex:
                self.log.error("Error in pipeline loop %d: %s", loop_count, ex)
                yield f"❌ {type(ex).__name__}: {ex}\n{''.join(traceback.format_exc(limit=5))}"
                break

            if pending_calls:
                results = await self._execute_tools(pending_calls, __tools__)
                for call, result in zip(pending_calls, results):
                    call_entry = {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                    output_entry = {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": str(result),
                    }
                    request_params["input"].append(call_entry)
                    request_params["input"].append(output_entry)
                    temp_input.insert(0, output_entry)
                    # TODO is there a better way to store tool results in conversation history?
                    await __event_emitter__({"type": "citation", "data": {"document": [f"{call.name}({call.arguments})\n\n{result}"], "metadata": [{"date_accessed": datetime.now().isoformat(), "source": call.name.replace("_", " ").title()}], "source": {"name": f"{call.name.replace('_', ' ').title()} Tool"}, "_fc": [{"call_id": call.call_id, "name": call.name, "arguments": call.arguments, "output": str(result)}]}})
                continue

            # Clean up the server-side state unless the user opted to keep it
            # TODO Ensure that the stored response is deleted.  Doesn't seem to work with LiteLLM Response API.
            remaining = self.valves.MAX_TOOL_CALLS - loop_count
            if loop_count == self.valves.MAX_TOOL_CALLS:
                request_params["tool_choice"] = "none"
                temp_input.append({"role": "assistant", "content": [{"type": "output_text", "text": f"[Internal thought] Final iteration ({loop_count}/{self.valves.MAX_TOOL_CALLS}). Tool-calling phase is over; I'll produce my final answer now."}]})
            elif loop_count == 2 and self.valves.MAX_TOOL_CALLS > 2:
                temp_input.append({"role": "assistant", "content": [{"type": "output_text", "text": f"[Internal thought] I've just received the initial tool results from iteration 1. I'm now continuing an iterative tool interaction with up to {self.valves.MAX_TOOL_CALLS} iterations."}]})
            elif remaining == 1:
                temp_input.append({"role": "assistant", "content": [{"type": "output_text", "text": f"[Internal thought] Iteration {loop_count}/{self.valves.MAX_TOOL_CALLS}. Next iteration is answer-only; any remaining tool calls must happen now."}]})
            elif loop_count > 2:
                temp_input.append({"role": "assistant", "content": [{"type": "output_text", "text": f"[Internal thought] Iteration {loop_count}/{self.valves.MAX_TOOL_CALLS} ({remaining} remaining, no action needed)."}]})
            break

        self.log.info(
            "CHAT_DONE chat=%s dur_ms=%.0f loops=%d in_tok=%d out_tok=%d total_tok=%d",
            __metadata__["chat_id"],
            (time.perf_counter_ns() - start_ns) / 1e6,
            usage_total.get("loops", 1),
            usage_total.get("input_tokens", 0),
            usage_total.get("output_tokens", 0),
            usage_total.get("total_tokens", 0),
        )

    async def _execute_tools(
        self, calls: list[SimpleNamespace], registry: dict[str, Any]
    ) -> list[Any]:
        """Run tool calls asynchronously and return their results."""
        tasks = []
        for call in calls:
            entry = registry.get(call.name)
            if entry is None:
                tasks.append(asyncio.create_task(asyncio.sleep(0, result="Tool not found")))
            else:
                args = json.loads(call.arguments or "{}")
                tasks.append(asyncio.create_task(entry["callable"](**args)))
        try:
            return await asyncio.gather(*tasks)
        except Exception as ex:
            self.log.error("Tool execution failed: %s", ex)
            return [f"Error: {ex}"] * len(tasks)

    def _apply_user_overrides(self, user_valves: BaseModel | None) -> None:
        """Override valve settings with user-provided values."""
        if not user_valves:
            return
        for setting, user_val in user_valves.model_dump(exclude_none=True).items():
            if isinstance(user_val, str) and user_val.lower() == "inherit":
                continue
            setattr(self.valves, setting, user_val)
            self.log.debug("User override → %s set to %r", setting, user_val)
        self.log.setLevel(getattr(logging, self.valves.CUSTOM_LOG_LEVEL.upper(), logging.INFO))

    def _build_params(
        self,
        body: dict[str, Any],
        instructions: str,
        tools: list[dict[str, Any]],
        user_email: str | None,
    ) -> dict[str, Any]:
        """Create the request payload for the Responses API."""
        params = {
            "model": self.valves.MODEL_ID,
            "tools": tools,
            "tool_choice": "auto" if tools else "none",
            "instructions": instructions,
            "parallel_tool_calls": self.valves.PARALLEL_TOOL_CALLS,
            "max_output_tokens": body.get("max_tokens"),
            "temperature": body.get("temperature") or 1.0,
            "top_p": body.get("top_p") or 1.0,
            "user": user_email,
            "text": {"format": {"type": "text"}},
            "truncation": "auto",
            "stream": True,
            "store": True,
        }
        if self.valves.REASON_EFFORT or self.valves.REASON_SUMMARY:
            params["reasoning"] = {}
            if self.valves.REASON_EFFORT:
                params["reasoning"]["effort"] = self.valves.REASON_EFFORT
            if self.valves.REASON_SUMMARY:
                params["reasoning"]["summary"] = self.valves.REASON_SUMMARY
        return params

    async def get_http_client(self) -> httpx.AsyncClient:
        """Return a shared httpx client."""
        if self._client and not self._client.is_closed:
            self.log.debug("Reusing existing httpx client.")
            return self._client
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                self.log.debug("Client initialized while waiting for lock. Reusing existing.")
                return self._client
            self.log.debug("Creating new httpx.AsyncClient.")
            timeout = httpx.Timeout(900.0, connect=30.0)
            self._client = httpx.AsyncClient(http2=True, timeout=timeout)
        return self._client

    @staticmethod
    def _extract_instructions(body: dict[str, Any]) -> str:
        """Return the last system message from the chat body."""
        return next(
            (
                m.get("content")
                for m in reversed(body.get("messages", []))
                if m.get("role") == "system"
            ),
            "",
        )

    @staticmethod
    def _update_usage(total: dict[str, Any], current: dict[str, Any], loops: int) -> None:
        """Aggregate token usage stats."""
        current = _to_dict(current)
        current["loops"] = loops
        for key, value in current.items():
            if key == "loops":
                continue
            if isinstance(value, int):
                total[key] = total.get(key, 0) + value
            elif isinstance(value, dict):
                total.setdefault(key, {})
                for subkey, subval in value.items():
                    total[key][subkey] = total[key].get(subkey, 0) + subval
        total["loops"] = loops


async def stream_responses(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    params: dict[str, Any],
) -> AsyncIterator[SimpleNamespace]:
    """Yield parsed SSE events from the Responses API."""

    url = base_url.rstrip("/") + "/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    async with client.stream("POST", url, headers=headers, json=params) as resp:
        resp.raise_for_status()
        event_type: str | None = None
        data_buf: list[str] = []
        async for raw in resp.aiter_lines():
            line = raw.rstrip("\r")
            if line.startswith(":"):
                continue
            if line == "":
                if data_buf:
                    data = "\n".join(data_buf)
                    if data.strip() == "[DONE]":
                        return
                    payload = json.loads(data)
                    yield _to_obj({"type": event_type or "message", **payload})
                event_type, data_buf = None, []
                continue
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_buf.append(line[len("data:"):].strip())


def _to_obj(data: Any) -> Any:
    """Recursively convert dictionaries to SimpleNamespace objects."""
    if isinstance(data, dict):
        return SimpleNamespace(**{k: _to_obj(v) for k, v in data.items()})
    if isinstance(data, list):
        return [_to_obj(v) for v in data]
    return data


def _to_dict(ns: Any) -> Any:
    """Recursively convert SimpleNamespace objects to dictionaries."""
    if isinstance(ns, SimpleNamespace):
        return {k: _to_dict(v) for k, v in vars(ns).items()}
    if isinstance(ns, list):
        return [_to_dict(v) for v in ns]
    if isinstance(ns, tuple):
        return tuple(_to_dict(v) for v in ns)
    return ns


def prepare_tools(registry: dict | None) -> list[dict]:
    """Convert WebUI tool registry entries to OpenAI format."""
    if not registry:
        return []
    raw = registry.get("tools", registry)
    tools_out = []
    for entry in raw.values():
        spec = entry.get("spec", entry)
        if "function" in spec:
            spec = spec["function"]
        tools_out.append(
            {
                "type": "function",
                "name": spec["name"],
                "description": spec.get("description", ""),
                "parameters": spec.get("parameters", {"type": "object"}),
            }
        )
    return tools_out


def build_responses_payload(chat_id: str) -> list[dict]:
    """Convert WebUI chat history to Responses API input format."""
    chat = Chats.get_chat_by_id(chat_id).chat
    msg_lookup = chat["history"]["messages"]
    current_id = chat["history"]["currentId"]
    thread: list[dict] = []
    while current_id:
        msg = msg_lookup[current_id]
        thread.append(msg)
        current_id = msg.get("parentId")
    thread.reverse()

    input_items: list[dict] = []
    for m in thread:
        role = m["role"]
        from_assistant = role == "assistant"
        if from_assistant:
            for src in m.get("sources", ()):
                for fc in src.get("_fc", ()):
                    cid = fc.get("call_id") or fc.get("id")
                    if not cid:
                        continue
                    input_items.append(
                        {
                            "type": "function_call",
                            "call_id": cid,
                            "name": fc.get("name") or fc.get("n"),
                            "arguments": fc.get("arguments") or fc.get("a"),
                        }
                    )
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": cid,
                            "output": fc.get("output") or fc.get("o"),
                        }
                    )
        blocks: list[dict] = []
        raw_blocks = m.get("content", []) or []
        if not isinstance(raw_blocks, list):
            raw_blocks = [raw_blocks]
        for b in raw_blocks:
            if b is None:
                continue
            text = b["text"] if isinstance(b, dict) else str(b)
            if from_assistant and not text.strip():
                continue
            blocks.append({"type": "output_text" if from_assistant else "input_text", "text": text})
        for f in m.get("files", ()):
            if f and f.get("type") in ("image", "image_url"):
                blocks.append({"type": "input_image" if role == "user" else "output_image", "image_url": f.get("url") or f.get("image_url", {}).get("url")})
        if blocks:
            input_items.append({"role": role, "content": blocks})
    return input_items


def pretty_log_block(data: Any, label: str = "") -> str:
    """Return a pretty formatted string for debug logging."""
    try:
        content = json.dumps(data, indent=2, default=str)
    except Exception:
        content = str(data)
    label_line = f"{label} =" if label else ""
    return f"\n{'-' * 40}\n{label_line}\n{content}\n{'-' * 40}"
