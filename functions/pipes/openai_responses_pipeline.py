"""
title: OpenAI Responses API Pipeline Test
id: openai_responses-test
author: Justin Kropp
author_url: https://github.com/jrkropp
funding_url: https://github.com/jrkropp/open-webui-developer-toolkit
description: Brings OpenAI Response API support to Open WebUI, enabling features not possible via Completions API.
version: 1.7.0
license: MIT
requirements: aiohttp, orjson
"""

import asyncio
import sys
import os
import aiohttp
import contextvars
import logging
import orjson

from fastapi import Request
from logging.handlers import MemoryHandler

# Pydantic for config classes
from pydantic import BaseModel, Field, field_validator
from typing import Any, AsyncGenerator, Awaitable, Callable, Literal

# Open WebUI Core imports
from open_webui.models.chats import Chats
from open_webui.models.files import Files
from open_webui.storage.provider import Storage

class Pipe:
    class Valves(BaseModel):
        BASE_URL: str = Field(
            default=os.getenv("OPENAI_API_BASE_URL").strip() or "https://api.openai.com/v1",
            description=(
                "The base URL to use with the OpenAI SDK. Defaults to the official "
                "OpenAI API endpoint. Supports LiteLLM and other custom endpoints."
            ),
        )

        API_KEY: str = Field(
            default=os.getenv("OPENAI_API_KEY").strip() or "sk-xxxxx",
            description="Your OpenAI API key. Defaults to the value of the OPENAI_API_KEY environment variable.",
        )

        MODEL_ID: str = Field(
            default="gpt-4.1, gpt-4o",
            description=(
                "Comma separated OpenAI model IDs. Each ID becomes a model entry in WebUI."
                " Supports the pseudo models 'o3-mini-high' and 'o4-mini-high', which map"
                " to 'o3-mini' and 'o4-mini' with reasoning effort forced to high."
            ),
        )

        REASON_SUMMARY: Literal["auto", "concise", "detailed", None] = Field(
            default=None,
            description=(
                "Reasoning summary style for o-series models (supported by: o3, o4-mini). Ignored for others."
                "Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning"
            ),
        )

        ENABLE_NATIVE_TOOL_CALLING: bool = Field(
            default=True,
            description="Enable native tool calling for supported models.",
        )

        ENABLE_WEB_SEARCH: bool = Field(
            default=False,
            description=(
                "Enable OpenAI's built-in 'web_search' tool when supported (gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini)."
                "Read more: https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses"
            ),
        )

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
            description=(
                "Whether tool calls can be parallelized. Defaults to True if not set."
                "Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-parallel_tool_calls"
            ),
        )

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
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "INHERIT"] = Field(
            default="INHERIT",
            description="Select logging level. 'INHERIT' uses the pipe default.",
        )

    def __init__(self):
        """
        Initialize default valves and placeholders.
        At this point, user-specific and global pipe valve values are NOT set. Only the global defaults are initialized.
        """
        # Holds per-request valve config using ContextVar — allows isolated overrides without affecting other requests
        self.valves = self.Valves()
        self.session: aiohttp.ClientSession | None = None
        self.log = logging.getLogger("openai_responses")
        if not self.log.handlers:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(
                logging.Formatter("%(levelname)-8s | %(name)-20s:%(lineno)-4d — %(message)s")
            )
            self.log.addHandler(ch)

    def pipes(self):
        """
        Return models exposed by this pipe and finalize client setup.
        At this point, global pipe values `self.valves` are set.
        """
        # Use valve value (with safe fallback) --------------------------------
        self.log.setLevel(getattr(logging, self.valves.CUSTOM_LOG_LEVEL.upper(), logging.INFO))

        models = [m.strip() for m in self.valves.MODEL_ID.split(",") if m.strip()]
        return [{"id": model, "name": f"OpenAI: {model}"} for model in models]
    # --------------------------------------------------
    #  3. Handling Inference/Generation (Main Method)
    # --------------------------------------------------

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any],
        __request__: Request,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __metadata__: dict[str, Any]
    ) -> AsyncGenerator[str, None] | str | None:
        """
        This method is called every time a user sends a chat request to an OpenAI model you exposed via `pipes()`.

        Steps:
          1) Updates valves and logging level based on user-specific overrides
          2) Parse the request body (model, messages, streaming, etc.)
          3) Construct the OpenAI request payload
          4) Decide to do streaming or single-shot generation
          5) Return or yield the final or partial responses to Open WebUI
        """

        # STEP 1: Setup
        valves = self._merge_valves(self.valves, __user__.get("valves", {})) # Merge user valve overrides (thread‑safe via ContextVar)
        self.session = await self._get_or_create_aiohttp_session()
        model_id = self._get_model_id(body)
        is_streaming = body.get("stream", False)
        user_messages = body.get("messages", [])
        pending_calls = []
        loop_count = 0
        max_loops = valves.MAX_TOOL_CALL_LOOPS
        final_output = ""

        # 2. Construct request payload for the OpenAI API
        openai_response_api_payload = {
            "model": model_id,
            "input": user_messages,
            "stream": is_streaming,
            # "temperature": body.get("temperature", 1.0),
            # ...
        }

        while loop_count < max_loops:
            loop_count += 1

            if is_streaming:
                self.log.info("Streaming mode enabled. Preparing to stream OpenAI responses.")
                async for event in self._stream_sse_events(
                        openai_response_api_payload,
                        valves.API_KEY,
                        valves.BASE_URL,
                    ):
                        et = event.get("type")

                        # Yield partial text
                        if et == "response.output_text.delta":
                            delta = event.get("delta", "")
                            if delta:
                                final_output += delta
                                #await __event_emitter__({"type": "chat:completion","data": {"content": final_output}})
                                yield delta  # Yielding partial text to Open WebUI

                        # Capture tool calls
                        if et == "response.output_item.done":
                            item = event.get("item")
                            if isinstance(item, dict):
                                pending_calls.append(item)

                        # Emit other info: annotations, reasoning, etc.
                        # (You already have this logic in a previous response)


                """
                await __event_emitter__({"type": "replace", "data": {"content":final_output, "done": True}})
                await __event_emitter__({"type": "chat:completion", "data": {"content":final_output,"done": True}})
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    chat_id=__metadata__.get("chat_id"),
                    message_id=__metadata__.get("message_id"),
                    content=final_output,
                    role="assistant",
                )
                """
                
            else:
                self.log.info("Non-streaming mode. Generating a synchronous response.")
                response_text = await self._non_streaming_response(
                    payload=openai_response_api_payload,
                    api_key=valves.API_KEY,
                    base_url=valves.BASE_URL
                )
                yield ""
            
            break # for now, we only handle one loop iteration
            if not pending_calls:
                break

    def _get_model_id(self, body):
        model_id = str(body["model"]).split(".", 1)[-1]
        if model_id in {"o3-mini-high", "o4-mini-high"}:
            body.setdefault("reasoning", {}).setdefault("effort", "high")
            model_id = model_id.replace("-high", "")
        return model_id
        
    # --------------------------------------------------
    #  4. Helpers (Streaming, Non-streaming, Logging, etc.)
    # --------------------------------------------------

    async def _stream_sse_events(
        self,
        request_params: dict[str, Any],
        api_key: str,
        base_url: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Streams SSE events from OpenAI's /responses endpoint and yields them ASAP.
        Optimized for low latency.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = base_url.rstrip("/") + "/responses"

        buf = bytearray()
        orjson_loads = orjson.loads

        async with self.session.post(url, json=request_params, headers=headers) as resp:
            resp.raise_for_status()

            async for chunk in resp.content.iter_any(): # parsing small chucks; may switch to iter_chunked(4096) if needed.
                buf.extend(chunk)
                while b"\n" in buf:
                    line, _, remainder = buf.partition(b"\n")
                    buf[:] = remainder
                    line = line.strip()

                    # SSE comment or empty line
                    if not line or line.startswith(b":"):
                        continue
                    # Must start with "data:"
                    if not line.startswith(b"data:"):
                        continue

                    data_part = line[5:].strip()
                    if data_part == b"[DONE]":
                        return  # End of SSE stream

                    yield orjson_loads(data_part)

    async def _non_streaming_response(
        self,
        payload: dict[str, Any],
        api_key: str,
        base_url: str
    ) -> str:
        """
        Single-shot call to the OpenAI Responses endpoint.
        Returns the assistant text (concatenated if multiple parts).
        Raises on HTTP or schema errors.
        """

        payload.pop("stream", None)  # Ensure not set

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        url = base_url.rstrip("/") + "/responses"
        self.log.debug("POST %s with payload: %s", url, payload)

        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    self.log.error("OpenAI /responses failed [%s]: %s", resp.status, error_text)
                    raise RuntimeError(f"OpenAI /responses error {resp.status}: {error_text}")

                raw_bytes = await resp.read()
                try:
                    data = orjson.loads(raw_bytes)
                except orjson.JSONDecodeError as e:
                    self.log.error("JSON decode error from /responses: %s", e)
                    self.log.debug("Raw response: %s", raw_bytes.decode(errors="replace"))
                    raise

        except aiohttp.ClientError as e:
            self.log.error("Network error calling /responses: %s", e)
            raise RuntimeError(f"Network error calling /responses: {e}") from e

        try:
            text_chunks: list[str] = []
            for item in data.get("output", []):
                if item.get("type") != "message":
                    continue  # Skip non-messages

                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text_chunks.append(part.get("text", ""))

            if not text_chunks:
                raise KeyError("assistant text not found in response")

            return "".join(text_chunks)

        except (KeyError, TypeError) as exc:
            self.log.error("Unexpected /responses schema: %s", exc)
            self.log.debug("Full response data: %s", data)
            raise

    async def _emit_error(
        self,
        message: str,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]]
    ):
        """
        Emits an event to the front-end that signals an error occurred.
        Adjust or rename to your needs.
        """
        error_event = {
            "type": "chat:completion",
            "data": {
                "error": {"detail": message},
                "done": True
            }
        }
        await event_emitter(error_event)

    def _merge_valves(self, global_valves, user_valves) -> "Pipe.Valves":
        """
        Merge user-level valves into default. 
        Ignores any user value set to "INHERIT" (case-insensitive).
        """
        if not user_valves:
            return global_valves

        # Merge: update only fields not set to "INHERIT"
        update = {
            k: v
            for k, v in user_valves.model_dump().items()
            if v is not None and str(v).lower() != "inherit"
        }
        return global_valves.model_copy(update=update)

    async def _get_or_create_aiohttp_session(self) -> aiohttp.ClientSession:
        """
        Get or create a reusable aiohttp.ClientSession with sane defaults.
        Call once in `pipes()`; keep it for the life of the process.
        """
        # Reuse existing session if available and open
        if self.session is not None and not self.session.closed:
            self.log.debug("Reusing existing aiohttp.ClientSession")
            return self.session
        
        self.log.debug("Creating new aiohttp.ClientSession")

        # Configure TCP connector for connection pooling and DNS caching
        connector = aiohttp.TCPConnector(
            limit=50,               # Max total simultaneous connections
            limit_per_host=10,      # Max connections per host
            keepalive_timeout=75,   # Seconds to keep idle sockets open
            ttl_dns_cache=300       # DNS cache time-to-live in seconds
        )

        # Set reasonable timeouts for connection and socket operations
        timeout = aiohttp.ClientTimeout(
            connect=30,             # Max seconds to establish connection
            sock_connect=30,        # Max seconds for socket connect
            sock_read=3600          # Max seconds for reading from socket (1 hour)
        )

        # Use orjson for fast JSON serialization
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            json_serialize=lambda obj: orjson.dumps(obj).decode()
        )

        return session