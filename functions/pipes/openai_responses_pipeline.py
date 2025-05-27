"""
title: OpenAI Responses API Pipeline
id: openai_responses
author: Justin Kropp
author_url: https://github.com/jrkropp
funding_url: https://github.com/jrkropp/open-webui-developer-toolkit
description: Brings OpenAI Response API support to Open WebUI, enabling features not possible via Completions API.
version: 1.6.25
license: MIT
requirements: httpx, orjson

------------------------------------------------------------------------------
🚀 CURRENT FEATURES
------------------------------------------------------------------------------
✅ o3/o4-mini o-series support (including visible <think> reasoning summaries)
✅ Image Input: Directly upload images into conversations.
✅ Built-in Web Search: Enabled via Pipe valve (powered by OpenAI web_search tool)
✅ Usage Stats: passthrough (to OpenWebUI GUI)
✅ Gateway Compatible: Supports LiteLLM and similar API gateways that support response API.
✅ Customizable logging: Set at a pipe or per-user level via Valves. If set to 'debug', adds citation for easy access.
✅ Optional injection of today's date and user context into the system prompt.
✅ Optimized Native Tool Calling:
   - True parallel tool calling support (i.e., gather multiple tool calls within a single turn and execute in parallel)
   - Live status updates showing running tools.
   - Tool outputs captured as citations for traceability & transparancy.
   - Persistent tool results (`function_call`/`function_call_output`) in conversation history (valve-controlled).
   - Automatically enables 'Native tool calling' in OpenWebUI model parm (if not set already).

------------------------------------------------------------------------------
🛠️ ROADMAP (PLANNED FEATURES)
------------------------------------------------------------------------------
⏳ Image Output: Direct generation of images using gpt-image-1 / dall-e-3 / dall-e-2
⏳ Document/File Input: Upload PDFs or other files directly as conversational context.
⏳ File Search Tool: Integration with OpenAI’s `file_search` feature.

------------------------------------------------------------------------------
🛠 CHANGE LOG
------------------------------------------------------------------------------
• 1.6.25: Clean up stale debug handlers before attaching new ones.
• 1.6.24: Apply log level overrides before attaching debug handler so updates
  take effect immediately.
• 1.6.23: Fixed user valve merging when CUSTOM_LOG_LEVEL is set to 'INHERIT'.
• 1.6.22: Added 'INHERIT' sentinel for CUSTOM_LOG_LEVEL.
• 1.6.21: User valves trimmed to CUSTOM_LOG_LEVEL; legacy 'inherit' handled.
• 1.6.20: Updated for Pydantic v2.
• 1.6.19: Added support for 'o3-mini-high' and 'o4-mini-high' model aliases.
• 1.6.18: Compatibility fixes for WebUI task models (optional chat_id and emitter).
• 1.6.17: Valves to inject the current date and user/device context into the system prompt.
• 1.6.16: Valve to control persisting tool results in chat history.
• 1.6.15: Added valve to toggle native tool calling; skips unsupported models; `reasoning_effort` now read directly from request body.
• 1.6.11: Disabled HTTP/2 to prevent stream stalls; optimized connection pooling.
• 1.6.10: Switched streaming from OpenAI SDK to direct HTTP via httpx; lightweight SSE parser added.
• 1.6.9: Updated dependency to `openai>=1.78.0`; introduced `UserValves` for per-user config overrides; enhanced logging.
• 1.6.8: Added granular `CUSTOM_LOG_LEVEL` control; refactored codebase for readability and maintenance.
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import inspect
import orjson
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime
from types import SimpleNamespace
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Literal

from starlette.requests import Request

import httpx
from open_webui.models.chats import Chats
from open_webui.models.models import Models, ModelForm, ModelParams
from open_webui.utils.misc import get_message_list
from pydantic import BaseModel, Field
from logging.handlers import BufferingHandler

EMOJI_LEVELS = {
    logging.DEBUG: "\U0001f50d",
    logging.INFO: "\u2139",
    logging.WARNING: "\u26a0",
    logging.ERROR: "\u274c",
    logging.CRITICAL: "\U0001f525",
}

# Feature support by model
# Defaults are assumed to be False for capabilities not listed.
MODEL_CAPABILITIES = {
    "gpt-4.1": {"web_search": True, "image_gen_tool": True, "function_calling": True},
    "gpt-4.1-mini": {
        "web_search": True,
        "image_gen_tool": True,
        "function_calling": True,
    },
    "gpt-4o": {"web_search": True, "image_gen_tool": True, "function_calling": True},
    "gpt-4o-mini": {
        "web_search": True,
        "image_gen_tool": True,
        "function_calling": True,
    },
    "gpt-4.1-nano": {"image_gen_tool": True, "function_calling": True},
    "o3": {"reasoning": True, "image_gen_tool": True, "function_calling": True},
    "o4-mini": {"reasoning": True, "function_calling": True},
    "o3-mini": {"reasoning": True, "function_calling": True},
    "chatgpt-4o-latest": {},
    "codex-mini-latest": {},
    "gpt-4o-search-preview": {},
    # Default (all False)
    "default": {
        "web_search": False,
        "image_gen_tool": False,
        "function_calling": False,
        "reasoning": False,
    },
}

# Precompiled regex for citation annotations
ANNOT_TITLE_RE = re.compile(r"title='([^']*)'")
ANNOT_URL_RE = re.compile(r"url='([^']*)'")


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
            default=os.getenv("OPENAI_API_KEY", "sk-xxxxx").strip(),
            description="Your OpenAI API key. Defaults to the value of the OPENAI_API_KEY environment variable.",
        )

        MODEL_ID: str = Field(
            default="gpt-4.1",
            description=(
                "Comma separated OpenAI model IDs. Each ID becomes a model entry in WebUI."
                " Supports the pseudo models 'o3-mini-high' and 'o4-mini-high', which map"
                " to 'o3-mini' and 'o4-mini' with reasoning effort forced to high."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-model

        REASON_SUMMARY: Literal["auto", "concise", "detailed", None] = Field(
            default=None,
            description=(
                "Reasoning summary style for o-series models (supported by: o3, o4-mini). Ignored for others."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning

        ENABLE_NATIVE_TOOL_CALLING: bool = Field(
            default=True,
            description="Enable native tool calling for supported models.",
        )

        ENABLE_WEB_SEARCH: bool = Field(
            default=False,
            description=(
                "Enable OpenAI's built-in 'web_search' tool when supported (gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini)."
            ),
        )  # Read more: https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses

        PERSIST_TOOL_RESULTS: bool = Field(
            default=True,
            description=(
                "Persist tool call results across conversation turns. When disabled,"
                " tool results are not stored in the chat history."
            ),
        )

        SEARCH_CONTEXT_SIZE: Literal["low", "medium", "high", None] = Field(
            default="medium",
            description=(
                "Specifies the OpenAI web search context size: low | medium | high. Default is 'medium'. Affects cost, quality, and latency. Only used if ENABLE_WEB_SEARCH=True."
            ),
        )

        ENABLE_IMAGE_GENERATION: bool = Field(
            default=False,
            description=("Enable the built-in 'image_generation' tool when supported."),
        )

        IMAGE_SIZE: str = Field(
            default="auto",
            description="Image width x height (e.g. 1024x1024 or 'auto').",
        )

        IMAGE_QUALITY: Literal["low", "medium", "high", "auto"] = Field(
            default="auto",
            description="Image rendering quality: low | medium | high | auto.",
        )

        IMAGE_FORMAT: Literal["png", "jpeg", "webp"] = Field(
            default="png",
            description="Return format for generated images.",
        )

        IMAGE_COMPRESSION: int | None = Field(
            default=None,
            ge=0,
            le=100,
            description="Compression level for jpeg/webp (0-100).",
        )

        IMAGE_BACKGROUND: Literal["transparent", "opaque", "auto"] = Field(
            default="auto",
            description="Background: transparent, opaque or auto.",
        )

        PARALLEL_TOOL_CALLS: bool = Field(
            default=True,
            description="Whether tool calls can be parallelized. Defaults to True if not set.",
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-parallel_tool_calls

        MAX_TOOL_CALL_LOOPS: int = Field(
            default=5,
            description=(
                "Maximum number of tool calls the model can make in a single request. This is a hard stop safety limit to prevent infinite loops. Defaults to 5."
            ),
        )

        STORE_RESPONSE: bool = Field(
            default=False,
            description=(
                "Whether to store the generated model response (on OpenAI's side) for later debugging. Defaults to False."
            ),
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-store

        CUSTOM_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
            Field(
                default=os.getenv("GLOBAL_LOG_LEVEL", "INFO").upper(),
                description="Select logging level.",
            )
        )

        INJECT_CURRENT_DATE: bool = Field(
            default=False,
            description=(
                "Append today's date to the system prompt. "
                "Example: `Today's date: Thursday, May 21, 2025`."
            ),
        )

        INJECT_USER_INFO: bool = Field(
            default=False,
            description=(
                "Append the user's name and email. "
                "Example: `user_info: Jane Doe <jane@example.com>`."
            ),
        )

        INJECT_BROWSER_INFO: bool = Field(
            default=False,
            description=(
                "Append browser details. "
                "Example: `browser_info: Desktop | Windows | Browser: Edge 136`."
            ),
        )

    class UserValves(BaseModel):
        """Per-user valve overrides."""

        CUSTOM_LOG_LEVEL: Literal[
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "INHERIT", None
        ] = Field(
            default="INHERIT",
            description="Select logging level. 'INHERIT' uses the pipe default.",
        )

    def __init__(self) -> None:
        """Initialize the pipeline."""
        self.valves = self.Valves()
        self.log_name = "OpenAI Responses"
        self.client: httpx.AsyncClient | None = None
        self.transport: httpx.AsyncHTTPTransport | None = None

    def pipes(self):
        """Return models exposed by this pipe."""
        models = [m.strip() for m in self.valves.MODEL_ID.split(",") if m.strip()]
        return [{"id": mid, "name": f"OpenAI: {mid}"} for mid in models]

    async def on_shutdown(self) -> None:
        """Clean up the HTTP client."""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            self.client = None
        if self.transport:
            await self.transport.aclose()
            self.transport = None

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
    ) -> None:
        """
        Stream responses from OpenAI and handle tool calls.
        """
        start_ns = time.perf_counter_ns()
        last_status: list[tuple[str, bool] | None] = [None]
        # inline merge default valves + per-user overrides (dropping "inherit")
        user_vals = __user__.get("valves")
        valves = self.valves.model_copy(
            update={
                k: v
                for k, v in (user_vals.model_dump().items() if user_vals else [])
                if str(v).lower() != "inherit"
            }
        )

        # Local logger for this request
        log_format = "%(emo)s %(levelname)-8s | %(name)-20s:%(lineno)-4d — %(message)s"
        log = logging.Logger(
            self.log_name, getattr(logging, valves.CUSTOM_LOG_LEVEL, logging.INFO)
        )
        log.propagate = False
        log.handlers[:] = [h := logging.StreamHandler(sys.stderr)]
        h.setFormatter(logging.Formatter(log_format))
        h.addFilter(
            lambda r: setattr(r, "emo", EMOJI_LEVELS.get(r.levelno, "❓")) or True
        )

        # Capture logs when DEBUG is enabled
        buf_handler: BufferingHandler | None = None
        if log.isEnabledFor(logging.DEBUG):
            # buffer up to 1000 records (or tune as you like)
            buf_handler = BufferingHandler(capacity=1000)
            buf_handler.setLevel(logging.DEBUG)
            buf_handler.setFormatter(h.formatter)  # reuse your same formatter
            buf_handler.addFilter(h.filters[0])  # reuse its filter
            log.addHandler(buf_handler)

        if valves.ENABLE_NATIVE_TOOL_CALLING:
            await self._enable_native_function_support(__metadata__, log)

        chat_id = __metadata__.get("chat_id")
        message_id = __metadata__.get("message_id")

        log.info(
            'CHAT_MSG pipe="%s" model=%s user=%s chat=%s message=%s',
            self.log_name,
            body.get("model", valves.MODEL_ID),
            __user__.get("email", "anon"),
            chat_id,
            message_id,
        )

        client = await self._get_http_client(log)

        request_params = await self._prepare_request_body(
            log,
            valves,
            body,
            chat_id,
            __user__,
            __request__,
        )
        usage_total: dict[str, Any] = {}
        last_response_id = None
        cleanup_ids: list[str] = []
        temp_input: list[dict[str, Any]] = []
        is_model_thinking = False
        loop_count = 0

        try:
            reasoning_summaries = ""

            for loop_count in range(1, valves.MAX_TOOL_CALL_LOOPS + 1):
                log.debug("Loop iteration #%d", loop_count)
                if loop_count > 1:
                    request_params.update(
                        {
                            "previous_response_id": last_response_id,
                            "input": temp_input,
                        }
                    )
                    temp_input = []

                pending_calls: list[SimpleNamespace] = []
                log.debug("Starting response stream (loop #%d)", loop_count)

                if request_params.get("reasoning") and not is_model_thinking:
                    is_model_thinking = True
                    yield "<think>"
                    """
                    await __event_emitter__(
                        {
                            "type": "replace",
                            "data": {
                                "content": "<details type='reasoning' done='false'>\n<summary>Thinking...</summary>\n> Preparing thoughts...\n</details>\n"
                            },
                        }
                    )
                    """

                async for event in self._stream_responses(
                    valves,
                    client,
                    request_params,
                ):
                    et = event.get("type")
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("Event received: %s", et)

                    if et == "response.created":
                        if last_response_id:
                            cleanup_ids.append(last_response_id)
                        last_response_id = event.get("response", {}).get("id")
                        continue
                    if et in {
                        "response.done",
                        "response.failed",
                        "response.incomplete",
                        "error",
                    }:
                        log.error("Stream ended with event: %s", et)
                        break
                    if et == "response.reasoning_summary_part.added":
                        # The <think> tag is emitted at stream start when
                        # reasoning is enabled. No action needed here.
                        continue
                    if et == "response.reasoning_summary_text.delta":
                        reasoning_summaries += event.get("delta", "")
                        await __event_emitter__(
                            {
                                "type": "replace",
                                "data": {
                                    "content": (
                                        "<details type='reasoning' done='false'>\n"
                                        "<summary>Thinking…</summary>\n"
                                        f"{reasoning_summaries}\n"
                                        "</details>\n"
                                    )
                                },
                            }
                        )
                        continue
                    if et == "response.reasoning_summary_text.done":
                        if reasoning_summaries:
                            reasoning_summaries += "\n----\n"
                        await __event_emitter__(
                            {
                                "type": "replace",
                                "data": {
                                    "content": (
                                        "<details type='reasoning' done='true'>\n"
                                        "<summary>Finished Reasoning</summary>\n"
                                        f"{reasoning_summaries}\n"
                                        "</details>\n"
                                    )
                                },
                            }
                        )
                        continue
                    if et == "response.content_part.added":
                        if is_model_thinking:
                            is_model_thinking = False
                            combined = reasoning_summaries.rstrip("-\n")
                            await __event_emitter__(
                                {
                                    "type": "replace",
                                    "data": {
                                        "content": (
                                            "<details type='reasoning' done='true'>\n"
                                            "<summary>Finished Reasoning</summary>\n"
                                            f"{combined}\n"
                                            "</details>\n"
                                        )
                                    },
                                }
                            )
                        continue
                    if et == "response.output_text.delta":
                        if __event_emitter__:
                            await __event_emitter__(
                                {
                                    "type": "chat:message:delta",
                                    "data": {"content": event.get("delta")},
                                }
                            )
                        continue
                    if et == "response.output_text.done":
                        continue
                    if et in {"response.image_generation_call.in_progress"}:
                        await self._emit_status(
                            __event_emitter__,
                            "🖼️ Generating image...",
                            last_status,
                        )
                        continue
                    if et == "response.image_generation_call.partial_image":
                        # TODO - ADD LOGIC HERE FOR EMITT.
                        continue
                    if et == "response.image_generation_call.completed":
                        await self._emit_status(
                            __event_emitter__,
                            "🖼️ Image generation completed",
                            last_status,
                            done=True,
                        )
                        continue
                    if et == "response.output_item.added":
                        item = event.get("item")
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "function_call"
                        ):
                            await self._emit_status(
                                __event_emitter__,
                                f"🔧 Running {item.get('name')}...",
                                last_status,
                            )
                        elif (
                            isinstance(item, dict)
                            and item.get("type") == "web_search_call"
                        ):
                            await self._emit_status(
                                __event_emitter__,
                                "🔍 Searching the internet...",
                                last_status,
                            )
                        elif (
                            isinstance(item, dict)
                            and item.get("type") == "image_generation_call"
                        ):
                            await self._emit_status(
                                __event_emitter__,
                                "🖼️ Generating image...",
                                last_status,
                            )
                        continue
                    if et == "response.output_item.done":
                        item = event.get("item")
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "function_call"
                        ):
                            pending_calls.append(SimpleNamespace(**item))
                            await self._emit_status(
                                __event_emitter__,
                                f"🔧 Running {item.get('name')}...",
                                last_status,
                                done=True,
                            )
                        elif (
                            isinstance(item, dict)
                            and item.get("type") == "web_search_call"
                        ):
                            await self._emit_status(
                                __event_emitter__,
                                "🔍 Searching the internet...",
                                last_status,
                                done=True,
                            )
                        elif (
                            isinstance(item, dict)
                            and item.get("type") == "image_generation_call"
                        ):
                            # TODO IMPLEMENT LOGIC FOR UPLOADING IMAGE TO FILES AND EMITTING IT
                            if __event_emitter__:
                                image_url = item.get("url")
                                if image_url:
                                    await __event_emitter__(
                                        {
                                            "type": "chat:message:files",
                                            "data": {
                                                "files": [
                                                    {"type": "image", "url": image_url}
                                                ]
                                            },
                                        }
                                    )
                                await self._emit_status(
                                    __event_emitter__,
                                    "🖼️ Image generation completed",
                                    last_status,
                                    done=True,
                                )
                        continue
                    if et == "response.output_text.annotation.added":
                        m = re.search(
                            r"title='([^']*)'.*?url='([^']*)'",
                            str(event.get("annotation", "")),
                        )
                        title, url = (
                            (m.group(1), m.group(2)) if m else ("Unknown Title", "")
                        )
                        url = url.replace("?utm_source=openai", "").replace(
                            "&utm_source=openai", ""
                        )
                        if __event_emitter__:
                            await __event_emitter__(
                                {
                                    "type": "citation",
                                    "data": {
                                        "document": [title],
                                        "metadata": [
                                            {
                                                "date_accessed": datetime.now().isoformat(),
                                                "source": title,
                                            }
                                        ],
                                        "source": {"name": url, "url": url},
                                    },
                                }
                            )
                        continue
                    if et == "response.completed":
                        usage = event.get("response", {}).get("usage")
                        if usage:
                            self._update_usage(usage_total, usage, loop_count)
                        continue

                if pending_calls:
                    results = await execute_responses_tool_calls(
                        pending_calls,
                        __tools__,
                        log,
                    )
                    for call, result in zip(pending_calls, results):
                        function_call_output = {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": str(result),
                        }
                        temp_input.insert(0, function_call_output)
                        if __event_emitter__:
                            citation_data = {
                                "document": [
                                    f"{call.name}({call.arguments})\n\n{result}"
                                ],
                                "metadata": [
                                    {
                                        "date_accessed": datetime.now().isoformat(),
                                        "source": call.name.replace("_", " ").title(),
                                    }
                                ],
                                "source": {
                                    "name": f"{call.name.replace('_', ' ').title()} Tool"
                                },
                            }
                            if valves.PERSIST_TOOL_RESULTS:
                                citation_data["_fc"] = [
                                    {
                                        "call_id": call.call_id,
                                        "name": call.name,
                                        "arguments": call.arguments,
                                        "output": str(result),
                                    }
                                ]
                            await __event_emitter__(
                                {"type": "citation", "data": citation_data}
                            )
                    remaining = valves.MAX_TOOL_CALL_LOOPS - loop_count
                    thought = ""
                    if loop_count == valves.MAX_TOOL_CALL_LOOPS:
                        request_params["tool_choice"] = "none"
                        thought = (
                            f"[Internal thought] Final iteration ({loop_count}/{valves.MAX_TOOL_CALL_LOOPS}). "
                            "Tool-calling phase is over; I'll produce my final answer now."
                        )
                    elif loop_count == 2 and valves.MAX_TOOL_CALL_LOOPS > 2:
                        thought = (
                            f"[Internal thought] I've just received the initial tool results from iteration 1. "
                            f"I'm now continuing an iterative tool interaction with up to {valves.MAX_TOOL_CALL_LOOPS} iterations."
                        )
                    elif remaining == 1:
                        thought = (
                            f"[Internal thought] Iteration {loop_count}/{valves.MAX_TOOL_CALL_LOOPS}. "
                            "Next iteration is answer-only; any remaining tool calls must happen now."
                        )
                    elif loop_count > 2:
                        thought = (
                            f"[Internal thought] Iteration {loop_count}/{valves.MAX_TOOL_CALL_LOOPS} "
                            f"({remaining} remaining, no action needed)."
                        )
                    if thought:
                        temp_input.append(
                            {
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": thought,
                                    }
                                ],
                            }
                        )
                        continue
                    continue

                if not pending_calls:
                    # Done with the iteration's tool calls, produce final output
                    break

        except Exception as ex:
            log.error("Error in pipeline loop %d: %s", loop_count, ex)
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "chat:message:delta",
                        "data": {
                            "content": f"\n\n❌ {type(ex).__name__}: {ex}\n{''.join(traceback.format_exc(limit=5))}",
                        },
                    }
                )

        finally:
            await self._emit_status(__event_emitter__, "", last_status, done=True)

            log.info(
                "CHAT_DONE chat=%s dur_ms=%.0f loops=%d in_tok=%d out_tok=%d total_tok=%d",
                chat_id,
                (time.perf_counter_ns() - start_ns) / 1e6,
                usage_total.get("loops", 1),
                usage_total.get("input_tokens", 0),
                usage_total.get("output_tokens", 0),
                usage_total.get("total_tokens", 0),
            )
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "chat:completion",
                        "data": {
                            "done": True,
                            **({"usage": usage_total} if usage_total else {}),
                        },
                    }
                )

            if last_response_id and not valves.STORE_RESPONSE:
                try:
                    await delete_response(
                        client,
                        valves.BASE_URL,
                        valves.API_KEY,
                        last_response_id,
                    )
                except Exception as ex:  # pragma: no cover - logging only
                    log.warning(
                        "Failed to delete response %s: %s", last_response_id, ex
                    )
            # Detach the in-memory handler
            if buf_handler:
                log.removeHandler(buf_handler)
                if buf_handler.buffer and __event_emitter__:
                    # format each record and join with newlines
                    formatted = [buf_handler.format(rec) for rec in buf_handler.buffer]
                    await __event_emitter__(
                        {
                            "type": "citation",
                            "data": {
                                "document": ["\n".join(formatted)],
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

    async def _build_chat_history_for_responses_api(
        self,
        log: logging.Logger,
        chat_id: str | None = None,
        messages: list[dict] | None = None,
    ) -> list[dict]:
        """Return chat history formatted for the Responses API."""
        from_history = bool(chat_id)
        if chat_id:
            log.debug("Retrieving message history for chat_id=%s", chat_id)
            chat_model = await asyncio.to_thread(Chats.get_chat_by_id, chat_id)
            if not chat_model:
                messages = []
            else:
                chat = chat_model.chat
                msg_lookup = chat.get("history", {}).get("messages", {})
                current_id = chat.get("history", {}).get("currentId")
                messages = get_message_list(msg_lookup, current_id) or []
        else:
            messages = messages or []

        history: list[dict] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                continue
            from_assistant = role == "assistant"

            if from_history and from_assistant:
                for src in m.get("sources", []):
                    for fc in src.get("_fc", []):
                        cid = fc.get("call_id") or fc.get("id")
                        if not cid:
                            continue
                        history.append(
                            {
                                "type": "function_call",
                                "call_id": cid,
                                "name": fc.get("name") or fc.get("n"),
                                "arguments": fc.get("arguments") or fc.get("a"),
                            }
                        )
                        history.append(
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
                if not b:
                    continue
                if isinstance(b, dict) and b.get("type") in ("image", "image_url"):
                    url = b.get("url") or b.get("image_url", {}).get("url")
                    if url:
                        blocks.append(
                            {
                                "type": (
                                    "input_image" if role == "user" else "output_image"
                                ),
                                "image_url": url,
                            }
                        )
                else:
                    text = b.get("text") if isinstance(b, dict) else str(b)
                    if from_history and from_assistant and not text.strip():
                        continue
                    if text.strip():
                        blocks.append(
                            {
                                "type": (
                                    "input_text" if role == "user" else "output_text"
                                ),
                                "text": text,
                            }
                        )

            if from_history:
                for f in m.get("files", []):
                    if f and f.get("type") in ("image", "image_url"):
                        blocks.append(
                            {
                                "type": (
                                    "input_image" if role == "user" else "output_image"
                                ),
                                "image_url": f.get("url")
                                or f.get("image_url", {}).get("url"),
                            }
                        )

            if blocks:
                history.append({"role": role, "content": blocks})

        return history

    async def _prepare_request_body(
        self,
        log: logging.Logger,
        valves: Pipe.Valves,
        body: dict[str, Any],
        chat_id: str | None = None,
        __user__: dict[str, Any] | None = None,
        __request__: Any = None,
    ) -> dict[str, Any]:
        """Assemble the JSON payload for the OpenAI Responses API."""
        # 1. Normalize model ID (handle *-high aliases)
        model_id = str(body["model"]).split(".", 1)[-1]
        if model_id in {"o3-mini-high", "o4-mini-high"}:
            body.setdefault("reasoning", {}).setdefault("effort", "high")
            model_id = model_id.replace("-high", "")

        # 2. Determine capabilities
        caps = MODEL_CAPABILITIES.get(model_id, MODEL_CAPABILITIES["default"])

        # 3. Tools
        if caps.get("function_calling") and valves.ENABLE_NATIVE_TOOL_CALLING:
            body["tools"] = transform_tools_for_responses_api(body.get("tools", []))
            if caps.get("web_search") and valves.ENABLE_WEB_SEARCH:
                body["tools"].append(
                    {
                        "type": "web_search",
                        "search_context_size": valves.SEARCH_CONTEXT_SIZE,
                    }
                )
            if caps.get("image_gen_tool") and valves.ENABLE_IMAGE_GENERATION:
                tool = {
                    "type": "image_generation",
                    "quality": valves.IMAGE_QUALITY,
                    "size": valves.IMAGE_SIZE,
                    "response_format": valves.IMAGE_FORMAT,
                    "background": valves.IMAGE_BACKGROUND,
                }
                if valves.IMAGE_COMPRESSION:
                    tool["output_compression"] = valves.IMAGE_COMPRESSION
                body["tools"].append(tool)
        else:
            body.pop("tools", None)
            log.debug("Native tool calling disabled or unsupported for %s", model_id)

        # 4. Reasoning
        if not caps.get("reasoning"):
            body.pop("reasoning", None)
        else:
            r = body.setdefault("reasoning", {})
            effort = body.get("reasoning_effort")
            if effort:
                r["effort"] = effort
            if valves.REASON_SUMMARY:
                r["summary"] = valves.REASON_SUMMARY

        # 5. Build instructions from system messages + any injected context
        instructions = next(
            (
                m["content"]
                for m in reversed(body.get("messages", []))
                if m["role"] == "system"
            ),
            "",
        )
        if valves.INJECT_CURRENT_DATE:
            instructions += (
                "\n\n" + "Today's date: " + datetime.now().strftime("%A, %B %d, %Y")
            )

        extras, notes = [], []
        if valves.INJECT_USER_INFO:
            extras.append(self._get_user_info_suffix(__user__))
            notes.append("`user_info`")
        if valves.INJECT_BROWSER_INFO:
            extras.append(self._get_browser_info_suffix(__request__))
            notes.append("`browser_info`")
        if extras:
            extras.append(
                "Note: "
                + ", ".join(notes)
                + " provided solely for AI contextual enrichment."
            )
            instructions += "\n\n" + "\n".join(extras)

        # 6. Final payload fields
        body.update(
            {
                "model": model_id,
                "instructions": instructions,
                "parallel_tool_calls": valves.PARALLEL_TOOL_CALLS,
                "user": __user__.get("email", "unknown"),
                "text": {"format": {"type": "text"}},
                "truncation": "auto",
                "store": True,
                "input": await self._build_chat_history_for_responses_api(log, chat_id),
                "tool_choice": "auto" if body.get("tools") else "none",
            }
        )

        # 7. Remove unsupported fields
        for field in ("stream_options", "messages", "reasoning_effort"):
            body.pop(field, None)

        return body

    async def _stream_responses(
        self,
        valves: Pipe.Valves,
        client: httpx.AsyncClient,
        request_params: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed SSE events from the API as dictionaries."""
        url = valves.BASE_URL.rstrip("/") + "/responses"
        headers = {
            "Authorization": f"Bearer {valves.API_KEY.strip()}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        loads = orjson.loads

        async with client.stream(
            "POST", url, headers=headers, json=request_params
        ) as response:
            response.raise_for_status()
            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        return
                    yield loads(data_str)

    async def _emit_status(
        self,
        emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        description: str,
        last_status: list[tuple[str, bool] | None],
        *,
        done: bool = False,
    ) -> None:
        """Emit a status update if it differs from the last one."""
        if emitter is None:
            return
        current = (description, done)
        if last_status[0] == current:
            return
        last_status[0] = current
        await emitter(
            {"type": "status", "data": {"description": description, "done": done}}
        )

    def _get_user_info_suffix(self, user: Dict[str, Any]) -> str:
        """Return a user_info line."""
        name = user.get("name") or ""
        email = user.get("email") or ""
        return f"user_info: {name} <{email}>"

    def _get_browser_info_suffix(self, request: Request | None) -> str:
        """Return a browser_info line."""
        headers = request.headers if request and hasattr(request, "headers") else {}
        mobile = str(headers.get("sec-ch-ua-mobile", "")).strip('"')
        device_type = "Mobile" if mobile in {"?1", "1"} else "Desktop"
        platform = headers.get("sec-ch-ua-platform", "").strip('"') or "Unknown"
        return (
            f"browser_info: {device_type} | {platform} | Browser: "
            f"{simplify_user_agent(headers.get('user-agent', '') if request else '')}"
        )

    async def _enable_native_function_support(
        self, metadata: dict[str, Any], log: logging.Logger
    ) -> None:
        """Ensure native function calling is enabled for the current model."""
        if metadata.get("function_calling") == "native":
            return

        model_dict = metadata.get("model") or {}
        model_id = model_dict.get("id") if isinstance(model_dict, dict) else model_dict
        model_capabilities = MODEL_CAPABILITIES.get(model_id, {})
        if not model_capabilities.get("function_calling"):
            log.debug("Model %s does not support native tool calling", model_id)
            return
        log.debug("Enabling native function calling for %s", model_id)

        model_info = (
            await asyncio.to_thread(Models.get_model_by_id, model_id)
            if model_id
            else None
        )
        if model_info:
            model_data = model_info.model_dump()
            model_data["params"]["function_calling"] = "native"
            model_data["params"] = ModelParams(**model_data["params"])
            updated = await asyncio.to_thread(
                Models.update_model_by_id, model_info.id, ModelForm(**model_data)
            )
            if updated:
                log.info("✅ Set model %s to native function calling", model_info.id)
            else:
                log.error("❌ Failed to update model %s", model_info.id)
        else:
            log.warning("⚠️ Model info not found for id %s", model_id)

        metadata["function_calling"] = "native"

    async def _get_http_client(self, log: logging.Logger) -> httpx.AsyncClient:
        """Return a shared httpx client."""
        if self.client and not self.client.is_closed:
            log.debug("Reusing existing httpx client.")
            return self.client

        log.debug("Creating new httpx.AsyncClient.")
        timeout = httpx.Timeout(900.0, connect=30.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=50)
        # HTTP/2 can stall if flow control windows aren't consumed quickly.
        # Using HTTP/1.1 avoids mid-stream pauses in high traffic scenarios.
        self.transport = httpx.AsyncHTTPTransport(http2=False, limits=limits)
        self.client = httpx.AsyncClient(transport=self.transport, timeout=timeout)
        return self.client

    @staticmethod
    def _update_usage(
        total: dict[str, Any], current: dict[str, Any], loops: int
    ) -> None:
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


def transform_tools_for_responses_api(tools: list[dict] | None) -> list[dict]:
    """
    Return a list of tools in which any nested dictionary matching tool["type"]
    is flattened into top-level fields. Only merges new fields; doesn't overwrite
    existing ones.
    """
    if not tools:
        return []

    transformed_tools = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue

        new_tool = dict(tool)

        tool_type = new_tool.get("type")
        if (
            tool_type
            and tool_type in new_tool
            and isinstance(new_tool[tool_type], dict)
        ):
            nested_data = new_tool.pop(tool_type)
            for k, v in nested_data.items():
                new_tool.setdefault(k, v)

        transformed_tools.append(new_tool)

    return transformed_tools


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
            args = orjson.loads(call.arguments or "{}")
            func = entry["callable"]
            if inspect.iscoroutinefunction(func):
                tasks.append(asyncio.create_task(func(**args)))
            else:
                tasks.append(asyncio.to_thread(func, **args))
    try:
        return await asyncio.gather(*tasks)
    except Exception as ex:  # pragma: no cover - log and return error results
        if log:
            log.error("Tool execution failed: %s", ex)
        return [f"Error: {ex}"] * len(tasks)


def simplify_user_agent(ua: str) -> str:
    """Return a short ``Browser Version`` string from ``ua``."""
    if not ua:
        return "Unknown"
    patterns = [
        (r"Edg(?:e|A)?/(?P<ver>[0-9.]+)", "Edge"),
        (r"OPR/(?P<ver>[0-9.]+)", "Opera"),
        (r"Chrome/(?P<ver>[0-9.]+)", "Chrome"),
        (r"Firefox/(?P<ver>[0-9.]+)", "Firefox"),
        (r"Version/(?P<ver>[0-9.]+).*Safari/", "Safari"),
        (r"Safari/(?P<ver>[0-9.]+)", "Safari"),
    ]
    for pat, name in patterns:
        m = re.search(pat, ua)
        if m:
            return f"{name} {m.group('ver').split('.')[0]}"
    return ua.split()[0]
