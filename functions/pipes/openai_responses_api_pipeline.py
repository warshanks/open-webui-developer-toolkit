"""
title: OpenAI Responses API Pipeline
id: openai_responses
author: Justin Kropp
author_url: https://github.com/jrkropp
description: Brings OpenAI Response API support to Open WebUI, enabling features not possible via Completions API.
version: 1.6.14
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
   - Set `MODEL_ID` to a comma separated list to expose multiple models.
   - Tool calling requires 'OpenWebUI Model Advanced Params → Function Calling → set to "Native"'

Read more about OpenAI Responses API:
- https://openai.com/index/new-tools-for-building-agents/
- https://platform.openai.com/docs/quickstart?api-mode=responses
- https://platform.openai.com/docs/api-reference/responses

-----------------------------------------------------------------------------
🛠
-----------------------------------------------------------------------------
• 1.6.11 (2025-05-17)
    - Disabled HTTP/2 to prevent mid-stream stalls
    - Optimized connection pooling for high concurrency
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
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Literal

import httpx
from fastapi import Request
from open_webui.models.chats import Chats
from open_webui.models.models import Models, ModelForm, ModelParams
from open_webui.utils.misc import deep_update, get_message_list
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

EMOJI_LEVELS = {
    logging.DEBUG: "\U0001F50D",
    logging.INFO: "\u2139",
    logging.WARNING: "\u26A0",
    logging.ERROR: "\u274C",
    logging.CRITICAL: "\U0001F525",
}

# Feature support by model
WEB_SEARCH_MODELS = {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"}
REASONING_MODELS = {"o3", "o4-mini"}

# Precompiled regex for citation annotations
ANNOT_TITLE_RE = re.compile(r"title='([^']*)'")
ANNOT_URL_RE = re.compile(r"url='([^']*)'")


@dataclass
class ResponsesEvent:
    """Parsed SSE event."""

    type: str
    delta: str | None = None
    text: str | None = None
    item_id: str | None = None
    item: Any | None = None
    response: Any | None = None


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
            default=os.getenv(
                "OPENAI_API_KEY", "sk-xxxxx"
            ).strip(),
            description="Your OpenAI API key. Defaults to the value of the OPENAI_API_KEY environment variable.",
        )

        MODEL_ID: str = Field(
            default="gpt-4.1",
            description=(
                "Comma separated OpenAI model IDs. Each ID becomes a model entry in WebUI."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-model

        REASON_SUMMARY: Literal["auto", "concise", "detailed", None] = Field(
            default=None,
            description=(
                "Reasoning summary style for o-series models (supported by: o3, o4-mini). Ignored for others."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning

        REASON_EFFORT: Literal["low", "medium", "high", None] = Field(
            default=None,
            description=(
                "Reasoning effort level for o-series models (supported by: o3, o4-mini)."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning

        ENABLE_WEB_SEARCH: bool = Field(
            default=False,
            description=(
                "Enable OpenAI's built-in 'web_search' tool when supported (gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini)."
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
        self.log_name = "OpenAI Responses"
        self._client: httpx.AsyncClient | None = None
        self._transport: httpx.AsyncHTTPTransport | None = None
        self._client_lock = asyncio.Lock()

        self.log = logging.getLogger(self.log_name)
        self.log.propagate = False
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(emo)s %(levelname)-8s | %(name)-20s:%(lineno)-4d — %(message)s"))
        handler.addFilter(lambda r: setattr(r, "emo", EMOJI_LEVELS.get(r.levelno, "\u2753")) or True)
        self._debug_logs: list[str] = []

        class _MemHandler(logging.Handler):
            def __init__(self, buf: list[str]) -> None:
                super().__init__(logging.DEBUG)
                self.buf = buf

            def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - trivial
                msg = self.format(record)
                self.buf.append(msg)

        mem_handler = _MemHandler(self._debug_logs)
        mem_handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
        self.log.handlers = [handler, mem_handler]
        self.log.setLevel(logging.INFO)
        self._last_status: tuple[str, bool] | None = None

    def pipes(self):
        """Return models exposed by this pipe."""
        models = [m.strip() for m in self.valves.MODEL_ID.split(',') if m.strip()]
        return [{"id": mid, "name": f"OpenAI: {mid}"} for mid in models]

    async def on_shutdown(self) -> None:
        """Clean up the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        if self._transport:
            await self._transport.aclose()
            self._transport = None

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
    ) -> AsyncIterator[str]:
        """
        Stream responses from OpenAI and handle tool calls.
        """
        start_ns = time.perf_counter_ns()
        self._last_status = None
        self._debug_logs.clear()
        self._apply_user_overrides(__user__.get("valves"))

        self._ensure_native_function_calling(__metadata__)

        self.log.info(
            'CHAT_MSG pipe="%s" model=%s user=%s chat=%s message=%s',
            self.log_name,
            body.get("model", self.valves.MODEL_ID),
            __user__.get("email", "anon"),
            __metadata__["chat_id"],
            __metadata__["message_id"],
        )

        client = await self.get_http_client()
        chat_id = __metadata__["chat_id"]
        input_messages = assemble_responses_input(chat_id)
        # TODO Consider setting the user system prompt (if specified) as a developer message rather than replacing the model system prompt.  Right now it get's the last instance of system message (user system prompt takes precidence)
        instructions = self._extract_instructions(body)

        model = body.get("model", self.valves.MODEL_ID.split(",")[0])
        if "." in str(model):
            model = str(model).split(".", 1)[1]

        tools = prepare_tools(__tools__)
        if self.valves.ENABLE_WEB_SEARCH and model in WEB_SEARCH_MODELS:
            tools.append(
                {
                    "type": "web_search",
                    "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,
                }
            )

        if self.log.isEnabledFor(logging.DEBUG):
            self.log.debug(pretty_log_block(tools, "tools"))
            self.log.debug(pretty_log_block(instructions, "instructions"))

        base_params = assemble_responses_payload(
            self.valves,
            chat_id,
            body,
            instructions,
            tools,
            __user__.get("email"),
        )
        request_params = base_params
        usage_total: dict[str, Any] = {}
        last_response_id = None
        cleanup_ids: list[str] = []
        temp_input: list[dict[str, Any]] = []
        is_model_thinking = False

        content = ""

        for loop_count in range(1, self.valves.MAX_TOOL_CALLS + 1):
            if self.log.isEnabledFor(logging.DEBUG):
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
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug(
                    pretty_log_block(
                        request_params.get("input", []),
                        f"turn_input_{loop_count}",
                    )
                )
                self.log.debug(
                    pretty_log_block(
                        request_params,
                        f"openai_request_params_{loop_count}",
                    )
                )

            try:
                pending_calls: list[SimpleNamespace] = []
                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug("response_stream created for loop #%d", loop_count)
                async for event in stream_responses(
                    client, self.valves.BASE_URL, self.valves.API_KEY, request_params
                ):
                    et = event.type
                    if self.log.isEnabledFor(logging.DEBUG):
                        self.log.debug("Event received: %s", et)

                    if et == "response.created":
                        if last_response_id:
                            cleanup_ids.append(last_response_id)
                        last_response_id = event.response.id
                        continue
                    if et in {"response.done", "response.failed", "response.incomplete", "error"}:
                        self.log.error("Stream ended with event: %s", et)
                        break
                    if et == "response.reasoning_summary_part.added":
                        if not is_model_thinking:
                            is_model_thinking = True
                            content += "<think>"
                            yield "<think>"
                        continue
                    if et == "response.reasoning_summary_text.delta":
                        content += event.delta
                        yield event.delta
                        continue
                    if et == "response.reasoning_summary_text.done":
                        content += "\n\n---\n\n"
                        yield "\n\n---\n\n"
                        continue
                    if et == "response.content_part.added":
                        if is_model_thinking:
                            is_model_thinking = False
                            content += "</think>\n"
                            yield "</think>\n"
                        continue
                    if et == "response.output_text.delta":
                        content += event.delta
                        yield event.delta
                        continue
                    if et == "response.output_text.done":
                        # This delta marks the end of the current output block.
                        continue
                    if et == "response.output_item.added":
                        item = getattr(event, "item", None)
                        if getattr(item, "type", None) == "function_call":
                            await self._emit_status(
                                __event_emitter__, f"🔧 Running {item.name}..."
                            )
                        elif getattr(item, "type", None) == "web_search_call":
                            await self._emit_status(
                                __event_emitter__, "🔍 Searching the internet..."
                            )
                        continue
                    if et == "response.output_item.done":
                        item = getattr(event, "item", None)
                        if getattr(item, "type", None) == "function_call":
                            pending_calls.append(item)
                            await self._emit_status(
                                __event_emitter__, f"🔧 Running {item.name}...", done=True
                            )
                        elif getattr(item, "type", None) == "web_search_call":
                            await self._emit_status(
                                __event_emitter__, "🔍 Searching the internet...", done=True
                            )
                        continue
                    if et == "response.output_text.annotation.added":
                        raw = str(getattr(event, "annotation", ""))
                        title_m = ANNOT_TITLE_RE.search(raw)
                        url_m = ANNOT_URL_RE.search(raw)
                        title = title_m.group(1) if title_m else "Unknown Title"
                        url = url_m.group(1) if url_m else ""
                        url = url.replace("?utm_source=openai", "").replace("&utm_source=openai", "")
                        await __event_emitter__({"type": "citation", "data": {"document": [title], "metadata": [{"date_accessed": datetime.now().isoformat(), "source": title}], "source": {"name": url, "url": url}}})
                        continue
                    if et == "response.completed":
                        if event.response.usage:
                            self._update_usage(
                                usage_total, event.response.usage, loop_count
                            )
                        continue
            except Exception as ex:
                self.log.error("Error in pipeline loop %d: %s", loop_count, ex)
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {
                            "content": f"❌ {type(ex).__name__}: {ex}\n{''.join(traceback.format_exc(limit=5))}",
                        },
                    }
                )
                break

            if pending_calls:
                results = await self._execute_tool_calls(pending_calls, __tools__)
                for call, result in zip(pending_calls, results):
                    function_call_output = {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": str(result),
                    }
                    temp_input.insert(0, function_call_output)
                    if __event_emitter__:
                        citation_event = {
                            "type": "citation",
                            "data": {
                                "document": [f"{call.name}({call.arguments})\n\n{result}"],
                                "metadata": [
                                    {
                                        "date_accessed": datetime.now().isoformat(),
                                        "source": call.name.replace("_", " ").title(),
                                    }
                                ],
                                "source": {"name": f"{call.name.replace('_', ' ').title()} Tool"},
                                "_fc": [
                                    {
                                        "call_id": call.call_id,
                                        "name": call.name,
                                        "arguments": call.arguments,
                                        "output": str(result),
                                    }
                                ],
                            },
                        }
                        await __event_emitter__(citation_event)
                continue

            # Clean up the server-side state unless the user opted to keep it
            # TODO Ensure that the stored response is deleted.  Doesn't seem to work with LiteLLM Response API.
            remaining = self.valves.MAX_TOOL_CALLS - loop_count
            if loop_count == self.valves.MAX_TOOL_CALLS:
                request_params["tool_choice"] = "none"
                entry = {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": f"[Internal thought] Final iteration ({loop_count}/{self.valves.MAX_TOOL_CALLS}). Tool-calling phase is over; I'll produce my final answer now.",
                        }
                    ],
                }
                temp_input.append(entry)
                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug(
                        "Appended to temp_input: %s",
                        json.dumps(entry, indent=2),
                    )
            elif loop_count == 2 and self.valves.MAX_TOOL_CALLS > 2:
                entry = {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": f"[Internal thought] I've just received the initial tool results from iteration 1. I'm now continuing an iterative tool interaction with up to {self.valves.MAX_TOOL_CALLS} iterations.",
                        }
                    ],
                }
                temp_input.append(entry)
                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug(
                        "Appended to temp_input: %s",
                        json.dumps(entry, indent=2),
                    )
            elif remaining == 1:
                entry = {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": f"[Internal thought] Iteration {loop_count}/{self.valves.MAX_TOOL_CALLS}. Next iteration is answer-only; any remaining tool calls must happen now.",
                        }
                    ],
                }
                temp_input.append(entry)
                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug(
                        "Appended to temp_input: %s",
                        json.dumps(entry, indent=2),
                    )
            elif loop_count > 2:
                entry = {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": f"[Internal thought] Iteration {loop_count}/{self.valves.MAX_TOOL_CALLS} ({remaining} remaining, no action needed).",
                        }
                    ],
                }
                temp_input.append(entry)
                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug(
                        "Appended to temp_input: %s",
                        json.dumps(entry, indent=2),
                    )
            break

        await self._emit_status(__event_emitter__, "", done=True)

        self.log.info(
            "CHAT_DONE chat=%s dur_ms=%.0f loops=%d in_tok=%d out_tok=%d total_tok=%d",
            __metadata__["chat_id"],
            (time.perf_counter_ns() - start_ns) / 1e6,
            usage_total.get("loops", 1),
            usage_total.get("input_tokens", 0),
            usage_total.get("output_tokens", 0),
            usage_total.get("total_tokens", 0),
        )

        if usage_total:
            await __event_emitter__(
                {"type": "chat:completion", "data": {"usage": usage_total}}
            )

        await __event_emitter__({"type": "chat:completion", "data": {"done": True}})

        for rid in cleanup_ids:
            try:
                await delete_response(
                    client,
                    self.valves.BASE_URL,
                    self.valves.API_KEY,
                    rid,
                )
            except Exception as ex:  # pragma: no cover - logging only
                self.log.warning("Failed to delete response %s: %s", rid, ex)

        if last_response_id and not self.valves.STORE_RESPONSE:
            try:
                await delete_response(
                    client,
                    self.valves.BASE_URL,
                    self.valves.API_KEY,
                    last_response_id,
                )
            except Exception as ex:  # pragma: no cover - logging only
                self.log.warning("Failed to delete response %s: %s", last_response_id, ex)

        if self.log.isEnabledFor(logging.DEBUG) and self._debug_logs:
            await __event_emitter__(
                {
                    "type": "citation",
                    "data": {
                        "document": ["\n".join(self._debug_logs)],
                        "metadata": [
                            {
                                "date_accessed": datetime.now().isoformat(),
                                "source": "Debug Logs",
                            }
                        ],
                        "source": {"name": "Debug Logs"},
                    },
                }
            )

    async def _execute_tool_calls(
        self, calls: list[SimpleNamespace], registry: dict[str, Any]
    ) -> list[Any]:
        """Run tool calls asynchronously and return their results."""
        return await execute_responses_tool_calls(calls, registry, self.log)

    async def _emit_status(
        self,
        emitter: Callable[[dict[str, Any]], Awaitable[None]],
        description: str,
        *,
        done: bool = False,
    ) -> None:
        """Emit a status update if it differs from the last one."""
        current = (description, done)
        if self._last_status == current:
            return
        self._last_status = current
        await emitter({"type": "status", "data": {"description": description, "done": done}})

    def _apply_user_overrides(self, user_valves: BaseModel | None) -> None:
        """Override valve settings with user-provided values."""
        if not user_valves:
            return

        dump = (
            user_valves.model_dump(exclude_none=True)
            if hasattr(user_valves, "model_dump")
            else user_valves.dict(exclude_none=True)
        )
        overrides = {
            k: v for k, v in dump.items() if not (isinstance(v, str) and v.lower() == "inherit")
        }

        base = (
            self.valves.model_dump()
            if hasattr(self.valves, "model_dump")
            else self.valves.dict()
        )
        updated = deep_update(base, overrides)
        self.valves = self.Valves(**updated)

        if self.log.isEnabledFor(logging.DEBUG):
            for setting, val in overrides.items():
                self.log.debug("User override → %s set to %r", setting, val)

        self.log.setLevel(
            getattr(logging, self.valves.CUSTOM_LOG_LEVEL.upper(), logging.INFO)
        )

    def _ensure_native_function_calling(self, metadata: dict[str, Any]) -> None:
        """Enable native function calling for a model if not already active."""
        if metadata.get("function_calling") == "native":
            return

        model_dict = metadata.get("model") or {}
        model_id = model_dict.get("id") if isinstance(model_dict, dict) else model_dict
        self.log.debug("Enabling native function calling for %s", model_id)

        model_info = Models.get_model_by_id(model_id) if model_id else None
        if model_info:
            model_data = model_info.model_dump()
            model_data["params"]["function_calling"] = "native"
            model_data["params"] = ModelParams(**model_data["params"])
            updated = Models.update_model_by_id(model_info.id, ModelForm(**model_data))
            if updated:
                self.log.info(
                    "✅ Set model %s to native function calling", model_info.id
                )
            else:
                self.log.error("❌ Failed to update model %s", model_info.id)
        else:
            self.log.warning("⚠️ Model info not found for id %s", model_id)

        metadata["function_calling"] = "native"


    async def get_http_client(self) -> httpx.AsyncClient:
        """Return a shared httpx client."""
        if self._client and not self._client.is_closed:
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug("Reusing existing httpx client.")
            return self._client
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug("Client initialized while waiting for lock. Reusing existing.")
                return self._client
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug("Creating new httpx.AsyncClient.")
            timeout = httpx.Timeout(900.0, connect=30.0)
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=50)
            # HTTP/2 can stall if flow control windows aren't consumed quickly.
            # Using HTTP/1.1 avoids mid-stream pauses in high traffic scenarios.
            self._transport = httpx.AsyncHTTPTransport(http2=False, limits=limits)
            self._client = httpx.AsyncClient(transport=self._transport, timeout=timeout)
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
        """Aggregate token usage stats without unnecessary conversions."""
        if isinstance(current, SimpleNamespace):
            current = vars(current)
        current = current or {}
        for key, value in current.items():
            if isinstance(value, SimpleNamespace):
                value = vars(value)
            if isinstance(value, (int, float)):
                total[key] = total.get(key, 0) + value
            elif isinstance(value, dict):
                inner = total.setdefault(key, {})
                for subkey, subval in value.items():
                    if isinstance(subval, (int, float)):
                        inner[subkey] = inner.get(subkey, 0) + subval
        total["loops"] = loops


async def stream_responses(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    params: dict[str, Any],
) -> AsyncIterator[ResponsesEvent]:
    """Yield parsed ``ResponsesEvent`` objects from the API."""

    url = base_url.rstrip("/") + "/responses"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
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
                    yield parse_responses_sse(event_type, data)
                event_type, data_buf = None, []
                continue
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_buf.append(line[len("data:"):].strip())
async def delete_response(
    client: httpx.AsyncClient, base_url: str, api_key: str, response_id: str
) -> None:
    """Delete a stored response."""
    url = base_url.rstrip("/") + f"/responses/{response_id}"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    resp = await client.delete(url, headers=headers)
    resp.raise_for_status()


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


def assemble_responses_input(chat_id: str) -> list[dict]:
    """Convert WebUI chat history to Responses API input format."""
    logger.debug("Retrieving message history for chat_id=%s", chat_id)
    chat = Chats.get_chat_by_id(chat_id).chat
    msg_lookup = chat["history"]["messages"]
    current_id = chat["history"]["currentId"]
    thread = get_message_list(msg_lookup, current_id) or []
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(pretty_log_block(thread, "history_thread"))

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


def assemble_responses_payload(
    valves: Pipe.Valves,
    chat_id: str,
    body: dict[str, Any],
    instructions: str,
    tools: list[dict[str, Any]],
    user_email: str | None,
) -> dict[str, Any]:
    """Combine chat history and parameters into a request payload."""
    model = body.get("model", valves.MODEL_ID.split(",")[0])
    if "." in str(model):
        model = str(model).split(".", 1)[1]
    params = {
        "model": model,
        "tools": tools,
        "tool_choice": "auto" if tools else "none",
        "instructions": instructions,
        "parallel_tool_calls": valves.PARALLEL_TOOL_CALLS,
        "max_output_tokens": body.get("max_tokens"),
        "temperature": body.get("temperature") or 1.0,
        "top_p": body.get("top_p") or 1.0,
        "user": user_email,
        "text": {"format": {"type": "text"}},
        "truncation": "auto",
        "stream": True,
        "store": True,
        "input": assemble_responses_input(chat_id),
    }

    if model in REASONING_MODELS and (valves.REASON_EFFORT or valves.REASON_SUMMARY):
        params["reasoning"] = {}
        if valves.REASON_EFFORT:
            params["reasoning"]["effort"] = valves.REASON_EFFORT
        if valves.REASON_SUMMARY:
            params["reasoning"]["summary"] = valves.REASON_SUMMARY

    return params


def parse_responses_sse(event_type: str | None, data: str) -> ResponsesEvent:
    """Parse an SSE data payload into a ``ResponsesEvent`` with minimal overhead."""
    loads = json.loads
    payload = loads(data)
    if "response" in payload and isinstance(payload["response"], dict):
        payload["response"] = SimpleNamespace(**payload["response"])
    if "item" in payload and isinstance(payload["item"], dict):
        payload["item"] = SimpleNamespace(**payload["item"])
    if "annotation" in payload and isinstance(payload["annotation"], dict):
        payload["annotation"] = SimpleNamespace(**payload["annotation"])

    event = ResponsesEvent(type=event_type or "message")
    for key, val in payload.items():
        setattr(event, key, val)
    return event


async def execute_responses_tool_calls(
    calls: list[SimpleNamespace],
    registry: dict[str, Any],
    log: logging.Logger | None = None,
) -> list[Any]:
    """Run tool calls asynchronously and return their results."""
    tasks: list[asyncio.Task] = []
    for call in calls:
        entry = registry.get(call.name)
        if entry is None:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result="Tool not found")))
        else:
            args = json.loads(call.arguments or "{}")
            tasks.append(asyncio.create_task(entry["callable"](**args)))
    try:
        return await asyncio.gather(*tasks)
    except Exception as ex:  # pragma: no cover - log and return error results
        if log:
            log.error("Tool execution failed: %s", ex)
        return [f"Error: {ex}"] * len(tasks)


