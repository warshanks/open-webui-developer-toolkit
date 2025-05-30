"""
title: OpenAI Responses API Pipeline Test
id: openai_responses_test
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
import logging
import orjson


from fastapi import Request
from io import StringIO

# Pydantic for config classes
from pydantic import BaseModel, Field, field_validator
from typing import Any, AsyncGenerator, Awaitable, Callable, Literal

# Open WebUI Core imports
from open_webui.models.chats import Chats
# from open_webui.tasks import list_task_ids_by_chat_id, stop_task, create_task, get_task
# from open_webui.models.files import Files
# from open_webui.storage.provider import Storage
from open_webui.models.models import Models, ModelForm, ModelParams
from open_webui.utils.misc import get_message_list

FEATURE_SUPPORT = {
    "web_search_tool": {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"}, # OpenAI's built-in web search tool.
    "image_gen_tool": {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "gpt-4.1-nano", "o3"}, # OpenAI's built-in image generation tool.
    "function_calling": {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "gpt-4.1-nano", "o3", "o4-mini", "o3-mini"}, # OpenAI's native function calling support.
    "reasoning": {"o3", "o4-mini", "o3-mini"}, # OpenAI's reasoning models.
    "reasoning_summary": {"o3", "o4-mini", "o3-mini"}, # OpenAI's reasoning summary feature.  May require OpenAI org verification before use.
}

class Pipe:
    class Valves(BaseModel):
        #TODO: Potential None.strip() Error.  To fix inline in future.
        BASE_URL: str = Field(
            default=os.getenv("OPENAI_API_BASE_URL").strip() or "https://api.openai.com/v1",
            description="The base URL to use with the OpenAI SDK. Defaults to the official OpenAI API endpoint. Supports LiteLLM and other custom endpoints.",
        )
        API_KEY: str = Field(
            default=os.getenv("OPENAI_API_KEY").strip() or "sk-xxxxx",
            description="Your OpenAI API key. Defaults to the value of the OPENAI_API_KEY environment variable.",
        )
        MODEL_ID: str = Field(
            default="gpt-4.1, gpt-4o",
            description="Comma separated OpenAI model IDs. Each ID becomes a model entry in WebUI. Supports the pseudo models 'o3-mini-high' and 'o4-mini-high', which map to 'o3-mini' and 'o4-mini' with reasoning effort forced to high.",
        )
        REASON_SUMMARY: Literal["auto", "concise", "detailed", None] = Field(
            default=None,
            description="Reasoning summary style for o-series models (supported by: o3, o4-mini). Ignored for others. Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning",
        )
        ENABLE_NATIVE_TOOL_CALLING: bool = Field(
            default=True,
            description="Enable native tool calling for supported models.",
        )
        ENABLE_WEB_SEARCH: bool = Field(
            default=False,
            description="Enable OpenAI's built-in 'web_search' tool when supported (gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini). Read more: https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses",
        )
        PERSIST_TOOL_RESULTS: bool = Field(
            default=True,
            description="Persist tool call results across conversation turns. When disabled, tool results are not stored in the chat history.",
        )
        SEARCH_CONTEXT_SIZE: Literal["low", "medium", "high", None] = Field(
            default="medium",
            description="Specifies the OpenAI web search context size: low | medium | high. Default is 'medium'. Affects cost, quality, and latency. Only used if ENABLE_WEB_SEARCH=True.",
        )
        ENABLE_IMAGE_GENERATION: bool = Field(
            default=False,
            description="Enable the built-in 'image_generation' tool when supported.",
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
            description="Whether tool calls can be parallelized. Defaults to True if not set. Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-parallel_tool_calls",
        )
        MAX_TOOL_CALL_LOOPS: int = Field(
            default=5,
            description="Maximum number of tool calls the model can make in a single request. This is a hard stop safety limit to prevent infinite loops. Defaults to 5.",
        )
        STORE_RESPONSE: bool = Field(
            default=False,
            description="Whether to store the generated model response (on OpenAI's side) for later debugging. Defaults to False.",
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-store
        CUSTOM_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
            default=os.getenv("GLOBAL_LOG_LEVEL", "INFO").upper(),
            description="Select logging level.",
        )
        INJECT_CURRENT_DATE: bool = Field(
            default=False,
            description="Append today's date to the system prompt. Example: `Today's date: Thursday, May 21, 2025`.",
        )
        INJECT_USER_INFO: bool = Field(
            default=False,
            description="Append the user's name and email. Example: `user_info: Jane Doe <jane@example.com>`.",
        )
        INJECT_BROWSER_INFO: bool = Field(
            default=False,
            description="Append browser details. Example: `browser_info: Desktop | Windows | Browser: Edge 136`.",
        )

    class UserValves(BaseModel):
        """Per-user valve overrides."""
        CUSTOM_LOG_LEVEL: Literal[
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "INHERIT"
        ] = Field(
            default="INHERIT",
            description="Select logging level. 'INHERIT' uses the pipe default.",
        )

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves() # Note: valve values are not accessible in __init__. Access from pipes() or pipe() methods.
        self.session: aiohttp.ClientSession | None = None
        self.log = logging.getLogger("openai_responses")
        if not self.log.handlers:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(
                logging.Formatter(
                    "%(levelname)-8s | %(name)-20s:%(lineno)-4d — %(message)s"
                )
            )
            self.log.addHandler(ch)

    def pipes(self):
        # Update logging level.
        self.log.setLevel(getattr(logging, self.valves.CUSTOM_LOG_LEVEL.upper(), logging.INFO))

        # return list of models to expose in Open WebUI
        models = [m.strip() for m in self.valves.MODEL_ID.split(",") if m.strip()]
        return [{"id": model, "name": f"OpenAI: {model}", "direct": True} for model in models]

    # --------------------------------------------------
    #  3. Handling Inference/Generation (Main Method)
    # --------------------------------------------------

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any],
        __request__: Request,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __metadata__: dict[str, Any],
    ) -> AsyncGenerator[str, None] | str | None:
        """
        This method is called every time a user sends a chat request to an OpenAI model you exposed via `pipes()`.
        """

        # Merge user valve overrides (thread‑safe via ContextVar)
        valves = self._merge_valves(self.valves, __user__.get("valves", {}))

        # Initialize aiohttp session (if not already done)
        self.session = await self._get_or_create_aiohttp_session()

        # 2. Construct request payload for the OpenAI API
        raw_model_id = str(body["model"]).split(".", 1)[-1]
        model_id = (
            raw_model_id.replace("-high", "")
            if raw_model_id in {"o3-mini-high", "o4-mini-high"}
            else raw_model_id
        )
        
        transformed_body = {
            "model": model_id,
            "instructions": next(
                (msg["content"] for msg in reversed(body.get("messages", [])) if msg.get("role") == "system"),
                "",
            ),
            "input": await self._build_chat_history_for_responses_api(__metadata__.get("chat_id")),
            "stream": body.get("stream", False),
            "user": __user__.get("email", "unknown_user"),
            "store": True,

            # Inline conditionals for optional parameters
            **({"temperature": body["temperature"]} if "temperature" in body else {}),
            **({"top_p": body["top_p"]} if "top_p" in body else {}),
            **({"max_tokens": body["max_tokens"]} if "max_tokens" in body else {}),
            
            # Inline conditional for tools:
            # Only include "tools" key if function calling is supported + enabled
            **(
                {
                    "tools": [
                        # Always include transformed user-provided tools
                        *self.transform_tools_for_responses_api(body.get("tools")),

                        # Optionally add web_search tool
                        *(
                            [self.web_search_tool(valves)]
                            if (model_id in FEATURE_SUPPORT["web_search_tool"] and valves.ENABLE_WEB_SEARCH)
                            else []
                        ),

                        # Optionally add image_generation tool
                        *(
                            [self.image_generation_tool(valves)]
                            if (model_id in FEATURE_SUPPORT["image_gen_tool"] and valves.ENABLE_IMAGE_GENERATION)
                            else []
                        ),
                    ]
                }
                if (model_id in FEATURE_SUPPORT["function_calling"] and valves.ENABLE_NATIVE_TOOL_CALLING)
                else {}
            ),
        }
        
        # If native tool calling is enabled, metadata is NOT native, and model supports native function calling
        # Body.tools is only populated if native function calling is enabled so tool calls will never be enabled the first iteration.  Determine if better method.
        # TODO THIS DOESN"T WORK YET.  NEED TO DEBUG WHY.
        if (
            valves.ENABLE_NATIVE_TOOL_CALLING
            and __metadata__.get("function_calling") != "native"
            and transformed_body["model"] in FEATURE_SUPPORT["function_calling"]
        ):
            await self._enable_native_function_support(transformed_body["model"], __metadata__)

        self.log.debug(
            "Constructed OpenAI request payload: %s", transformed_body
        )

        self.log.debug(
            "[TOOL DEBUG] model=%s | function_calling=%s | native_enabled=%s | web_enabled=%s | web_ok=%s | img_enabled=%s | img_ok=%s | user_tools=%s",
            model_id,
            model_id in FEATURE_SUPPORT["function_calling"],
            valves.ENABLE_NATIVE_TOOL_CALLING,
            valves.ENABLE_WEB_SEARCH,
            model_id in FEATURE_SUPPORT["web_search_tool"],
            valves.ENABLE_IMAGE_GENERATION,
            model_id in FEATURE_SUPPORT["image_gen_tool"],
            bool(body.get("tools")),
        )

        final_output = StringIO()
        pending_calls = []

        # Loop until there are no remaining tool calls or we hit the max loop count
        for loop_count in range(valves.MAX_TOOL_CALL_LOOPS):
            if transformed_body["stream"]:
                # Streaming mode: yield partial responses to UI as they arrive
                async for event in self._stream_sse_events(
                    transformed_body,
                    valves.API_KEY,
                    valves.BASE_URL,
                ):
                    et = event.get("type")

                    # Yield partial text
                    if et == "response.output_text.delta":
                        delta = event.get("delta", "")
                        if delta:
                            final_output.write(delta) # Append to final output. TBD If we use this.
                            yield delta  # Yielding partial text to Open WebUI

                    # Capture tool calls
                    if et == "response.output_item.done":
                        item = event.get("item")
                        if isinstance(item, dict):
                            pending_calls.append(item)

                    # Emit other info: annotations, reasoning, etc.
                    # (You already have this logic in a previous response)

                # await asyncio.sleep(0.05)

                self.log.debug("Streaming complete. Finalizing response. Chat ID: %s, Message ID: %s",
                    __metadata__.get("chat_id", "unknown_chat"),
                    __metadata__.get("message_id", "unknown_message"),
                )

            else:
                self.log.info("Non-streaming mode. Generating a synchronous response.")
                response_text = await self._non_streaming_response(
                    payload=transformed_body,
                    api_key=valves.API_KEY,
                    base_url=valves.BASE_URL,
                )
                yield response_text

            break  # for now, we only handle one loop iteration
            if not pending_calls:
                break

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
        orjson_loads = orjson.loads  # Cached reference for speed
        async with self.session.post(url, json=request_params, headers=headers) as resp:
            resp.raise_for_status()

            async for chunk in resp.content.iter_chunked(4096):
                buf.extend(chunk)
                start_idx = 0
                # Process all complete lines in the buffer
                while True:
                    newline_idx = buf.find(b"\n", start_idx)
                    if newline_idx == -1:
                        break
                    
                    line = buf[start_idx:newline_idx].strip()
                    start_idx = newline_idx + 1

                    # Skip empty lines, comment lines, or anything not starting with "data:"
                    if (not line or line.startswith(b":") or not line.startswith(b"data:")):
                        continue

                    data_part = line[5:].strip()
                    if data_part == b"[DONE]":
                        return  # End of SSE stream
                    
                    # Yield JSON-decoded data
                    yield orjson_loads(data_part)

                # Remove processed data from the buffer
                if start_idx > 0:
                    del buf[:start_idx]

    async def _non_streaming_response(
        self, payload: dict[str, Any], api_key: str, base_url: str
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
                    self.log.error(
                        "OpenAI /responses failed [%s]: %s", resp.status, error_text
                    )
                    raise RuntimeError(
                        f"OpenAI /responses error {resp.status}: {error_text}"
                    )

                raw_bytes = await resp.read()
                try:
                    data = orjson.loads(raw_bytes)
                except orjson.JSONDecodeError as e:
                    self.log.error("JSON decode error from /responses: %s", e)
                    self.log.debug(
                        "Raw response: %s", raw_bytes.decode(errors="replace")
                    )
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
        self, message: str, event_emitter: Callable[[dict[str, Any]], Awaitable[None]]
    ):
        """
        Emits an event to the front-end that signals an error occurred.
        Adjust or rename to your needs.
        """
        error_event = {
            "type": "chat:completion",
            "data": {"error": {"detail": message}, "done": True},
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
            limit=50,  # Max total simultaneous connections
            limit_per_host=10,  # Max connections per host
            keepalive_timeout=75,  # Seconds to keep idle sockets open
            ttl_dns_cache=300,  # DNS cache time-to-live in seconds
        )

        # Set reasonable timeouts for connection and socket operations
        timeout = aiohttp.ClientTimeout(
            connect=30,  # Max seconds to establish connection
            sock_connect=30,  # Max seconds for socket connect
            sock_read=3600,  # Max seconds for reading from socket (1 hour)
        )

        # Use orjson for fast JSON serialization
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            json_serialize=lambda obj: orjson.dumps(obj).decode(),
        )

        return session
    
    async def _enable_native_function_support(
        self, model_id: str, metadata: dict[str, Any]
    ) -> None:
        """Enable native function calling for the given model, if supported."""
        if metadata.get("function_calling") == "native":
            return

        if model_id not in FEATURE_SUPPORT["function_calling"]:
            self.log.debug("Model %s does not support native tool calling", model_id)
            return

        self.log.debug("Enabling native function calling for %s", model_id)

        model_info = await asyncio.to_thread(Models.get_model_by_id, model_id)
        if not model_info:
            self.log.warning("⚠️ Model info not found for id %s", model_id)
            return

        model_data = model_info.model_dump()
        model_data["params"]["function_calling"] = "native"
        model_data["params"] = ModelParams(**model_data["params"])

        updated = await asyncio.to_thread(
            Models.update_model_by_id, model_info.id, ModelForm(**model_data)
        )
        if updated:
            self.log.info("✅ Set model %s to native function calling", model_info.id)
            metadata["function_calling"] = "native"  # ✅ CRITICAL
        else:
            self.log.error("❌ Failed to update model %s", model_info.id)

    @staticmethod
    def transform_tools_for_responses_api(tools: list[dict] | None, __metadata__: dict[str, Any] | None = None) -> list[dict]:
        """Transform user-provided tools (or return an empty list)."""
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

    @staticmethod
    def web_search_tool(valves) -> dict:
        """Build a web_search tool dictionary."""
        return {"type": "web_search", "search_context_size": valves.SEARCH_CONTEXT_SIZE}

    @staticmethod
    def image_generation_tool(valves) -> dict:
        """Build an image_generation tool dictionary."""
        tool = {
            "type": "image_generation",
            "quality": valves.IMAGE_QUALITY,
            "size": valves.IMAGE_SIZE,
            "response_format": valves.IMAGE_FORMAT,
            "background": valves.IMAGE_BACKGROUND,
        }
        if valves.IMAGE_COMPRESSION:
            tool["output_compression"] = valves.IMAGE_COMPRESSION
        return tool
    
    async def _build_chat_history_for_responses_api(
        self,
        chat_id: str | None = None,
    ) -> list[dict]:
        """Return chat history formatted for the Responses API."""
        from_history = bool(chat_id)
        if chat_id:
            self.log.debug("Retrieving message history for chat_id=%s", chat_id)
            chat_model = await asyncio.to_thread(Chats.get_chat_by_id, chat_id)
            if not chat_model:
                messages = []
            else:
                chat = chat_model.chat
                msg_lookup = chat.get("history", {}).get("messages", {})
                current_id = chat.get("history", {}).get("currentId")
                messages = get_message_list(msg_lookup, current_id) or []
        else:
            messages = []

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
