"""
title: OpenAI Responses API Manifold
id: openai_responses
author: Justin Kropp
author_url: https://github.com/jrkropp
funding_url: https://github.com/jrkropp/open-webui-developer-toolkit
description: Brings OpenAI Response API support to Open WebUI, enabling features not possible via Completions API.
version: 0.8.0
license: MIT
requirements: orjson
"""


import asyncio
from collections import defaultdict
import datetime
import inspect
import json
import random
import re
import sys
import os
import aiohttp
import logging
import orjson
from typing import Optional, Dict, Any, List

from contextvars import ContextVar
from fastapi import Request
from io import StringIO

# Pydantic for config classes
from pydantic import BaseModel, Field
from typing import AsyncGenerator, Awaitable, Callable, Literal

# Open WebUI Core imports
from open_webui.models.chats import Chats, ChatModel
# from open_webui.models.files import Files
# from open_webui.storage.provider import Storage
from open_webui.models.models import Models, ModelForm, ModelParams
from open_webui.utils.misc import get_message_list

FEATURE_SUPPORT = {
    "web_search_tool": {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"}, # OpenAI's built-in web search tool.
    "image_gen_tool": {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "gpt-4.1-nano", "o3"}, # OpenAI's built-in image generation tool.
    "function_calling": {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "gpt-4.1-nano", "o3", "o4-mini", "o3-mini"}, # OpenAI's native function calling support.
    "reasoning": {"o3", "o4-mini", "o3-mini"}, # OpenAI's reasoning models.
    "reasoning_summary": {"o3", "o4-mini", "o4-mini-high", "o3-mini", "o3-mini-high" }, # OpenAI's reasoning summary feature.  May require OpenAI org verification before use.
}

# A global context var storing the current message ID
current_session_id = ContextVar("current_session_id", default=None)

# Log level ContextVar (defaults to INFO)
current_log_level = ContextVar("current_log_level", default=logging.INFO)

# In-memory logs keyed by message ID
logs_by_msg_id = defaultdict(list)

# Precompiled regex for stripping <details> blocks from assistant text
DETAILS_RE = re.compile(r"<details\b[^>]*>.*?<\/details>", flags=re.S | re.I)

class Pipe:
    class Valves(BaseModel):
        BASE_URL: str = Field(
            default=((os.getenv("OPENAI_API_BASE_URL") or "").strip() or "https://api.openai.com/v1"),
            description="The base URL to use with the OpenAI SDK. Defaults to the official OpenAI API endpoint. Supports LiteLLM and other custom endpoints.",
        )
        API_KEY: str = Field(
            default=(os.getenv("OPENAI_API_KEY") or "").strip() or "sk-xxxxx",
            description="Your OpenAI API key. Defaults to the value of the OPENAI_API_KEY environment variable.",
        )
        MODEL_ID: str = Field(
            default="gpt-4.1, gpt-4o",
            description="Comma separated OpenAI model IDs. Each ID becomes a model entry in WebUI. Supports the pseudo models 'o3-mini-high' and 'o4-mini-high', which map to 'o3-mini' and 'o4-mini' with reasoning effort forced to high.",
        )
        ENABLE_REASONING_SUMMARY: Literal["auto", "concise", "detailed", None] = Field(
            default=None,
            description="Reasoning summary style for o-series models (supported by: o3, o4-mini). Ignored for others. Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-reasoning",
        )
        ENABLE_WEB_SEARCH: bool = Field(
            default=False,
            description="Enable OpenAI's built-in 'web_search' tool when supported (gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini).  Note this adds the tool to each call which may slow down responses. Read more: https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses",
        )
        SEARCH_CONTEXT_SIZE: Literal["low", "medium", "high", None] = Field(
            default="medium",
            description="Specifies the OpenAI web search context size: low | medium | high. Default is 'medium'. Affects cost, quality, and latency. Only used if ENABLE_WEB_SEARCH=True.",
        )
        SEARCH_USER_LOCATION: str = Field(
            default='{"type": "approximate", "country": "CA", "city": "Langley", "region": "BC"}',
            description="User location for web search. Defaults to approximate London, UK. Read more: https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses#user-location",
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
        PERSIST_TOOL_RESULTS: bool = Field(
            default=True,
            description="Persist tool call results across conversation turns. When disabled, tool results are not stored in the chat history.",
        )
        STORE_RESPONSE: bool = Field(
            default=False,
            description="Whether to store the generated model response (on OpenAI's side) for later debugging. Defaults to False.",
        )  # Read more: https://platform.openai.com/docs/api-reference/responses/create#responses-create-store
        INJECT_CURRENT_DATE: bool = Field(
            default=False,
            description="Append today's date to the system prompt. Example: `Today's date: Thursday, May 21, 2025`.",
        )
        INJECT_USER_INFO: bool = Field(
            default=False,
            description="Append the user's name and email. Example: `user_info: Jane Doe <jane@example.com>`.",
        )
        LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
            default=os.getenv("GLOBAL_LOG_LEVEL", "INFO").upper(),
            description="Select logging level.  Recommend INFO or WARNING for production use. DEBUG is useful for development and debugging.",
        )

    class UserValves(BaseModel):
        """Per-user valve overrides."""
        LOG_LEVEL: Literal[
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "INHERIT"
        ] = Field(
            default="INHERIT",
            description="Select logging level. 'INHERIT' uses the pipe default.",
        )

    class SelfTerminate(Exception):
        """Intentionally raised to terminate task early without triggering CancelledError logic."""
        pass

    def __init__(self):
        self.type = "manifold"

        self.valves = self.Valves()  # Note: valve values are not accessible in __init__. Access from pipes() or pipe() methods.
        self.session: aiohttp.ClientSession | None = None
        self.log = logging.getLogger(__name__)
        # Prevent propagation to the root logger which may add its own handlers
        self.log.propagate = False
        # Set to DEBUG so per-message filtering controls output
        self.log.setLevel(logging.DEBUG)

        # Add an inline "filter" that injects `session_id` into each record
        self.log.addFilter(
            lambda record: (
                setattr(
                    record,
                    "session_id",
                    getattr(record, "session_id", None) or current_session_id.get(),
                )
                or True
            )
        )

        # Filter logs based on the ContextVar-controlled log level
        def _per_message_level(record, logger=self.log):
            return record.levelno >= current_log_level.get(logger.level)

        self.log.addFilter(_per_message_level)

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter(
            "%(levelname)s [mid=%(session_id)s] %(message)s"
        ))
        self.log.addHandler(console)

        mem_handler = logging.Handler()
        mem_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))

        # Inline emit function:
        mem_handler.emit = lambda record: (
            # Only proceed if record has a session_id
            logs_by_msg_id.setdefault(getattr(record, "session_id", None), [])
                        .append(mem_handler.format(record))
            if getattr(record, "session_id", None)
            else None
        )

        self.log.addHandler(mem_handler)
    
    def pipes(self):
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
        __tools__: list[dict[str, Any]] | dict[str, Any] | None
    ) -> AsyncGenerator[str, None] | str | None:
        """
        This method is called every time a user sends a chat request to an OpenAI model you exposed via `pipes()`.
        """
        # Get the current message ID from contextvars
        chat_id = __metadata__.get("chat_id", None)
        session_id = __metadata__.get("session_id", None)
        message_id = __metadata__.get("message_id", None)
        token = current_session_id.set(session_id)

        # Merge user valve overrides (thread‑safe via ContextVar)
        user_valves = self.UserValves.model_validate(__user__.get("valves", {}))
        valves = self._merge_valves(self.valves, user_valves)

        # Update per-message log level via ContextVar
        log_token = current_log_level.set(
            getattr(logging, valves.LOG_LEVEL.upper(), logging.INFO)
        )

        # Init variables before entering the main loop
        final_output = StringIO()
        loop_count = -1
        collected_items: list[dict[str, Any]] = []
        calls_to_execute: list[dict[str, Any]] = []
        total_usage = {}
        reasoning_map = {}  # Stores reasoning text per summary_index

        try:
            self.session = await self._get_or_create_aiohttp_session() # aiohttp is used for performance (vs. httpx).

            # Build the OpenAI Responses API request body
            model_id = str(body["model"]).split(".", 1)[-1]
            if model_id in {"o3-mini-high", "o4-mini-high"}:
                model_id = model_id.replace("-high", "")  # Remove "-high" suffix
                body["reasoning_effort"] = "high"  # Force high reasoning effort

            transformed_body = {
                "model": model_id,
                "instructions": next((msg["content"] for msg in reversed(body.get("messages", [])) if msg.get("role") == "system"), ""),
                "input": build_responses_history_by_chat_id_and_message_id(
                    chat_id,
                    message_id,
                    model_id=model_id,
                ),
                "stream": body.get("stream", False),
                "user": __user__.get("email", "unknown_user"),
                "store": valves.STORE_RESPONSE,

                # Inline conditionals for optional parameters
                **({"temperature": body["temperature"]} if "temperature" in body else {}),
                **({"top_p": body["top_p"]} if "top_p" in body else {}),
                **({"max_tokens": body["max_tokens"]} if "max_tokens" in body else {}),
                **({"parallel_tool_calls": valves.PARALLEL_TOOL_CALLS} if valves.PARALLEL_TOOL_CALLS else {}),

                # Conditionally add tools only if function calling is supported and enabled
                **(
                    {
                        "tools": [
                            *self.transform_tools_for_responses_api(__tools__),

                            # Conditionally include web_search
                            *(
                                [self.web_search_tool(valves)]
                                if (model_id in FEATURE_SUPPORT["web_search_tool"] and (valves.ENABLE_WEB_SEARCH ))
                                else []
                            ),

                            # Conditionally include image_generation
                            *(
                                [self.image_generation_tool(valves)]
                                if (model_id in FEATURE_SUPPORT["image_gen_tool"] and valves.ENABLE_IMAGE_GENERATION)
                                else []
                            ),
                        ]
                    }
                    if model_id in FEATURE_SUPPORT["function_calling"]
                    else {}
                ),

                # Conditionally add reasoning dict if the model supports reasoning AND (effort or summary) was specified
                **(
                    {
                        "reasoning": {
                            **({"effort": body["reasoning_effort"]} if "reasoning_effort" in body else {}),
                            **(
                                {"summary": valves.ENABLE_REASONING_SUMMARY}
                                if (
                                    valves.ENABLE_REASONING_SUMMARY
                                    and model_id in FEATURE_SUPPORT["reasoning_summary"]
                                )
                                else {}
                            ),
                        }
                    }
                    if (model_id in FEATURE_SUPPORT["reasoning"]) else {}
                ),

                # Only include "include" if it's a reasoning model. Included encrypted reasoning tokens (important for multi-turn loops).
                **(
                    {
                        "include": ["reasoning.encrypted_content"]
                    }
                    if model_id in FEATURE_SUPPORT["reasoning"]
                    else {}
                ),
            }

            # Log transformed_body
            self.log.debug("Transformed OpenAI request body: %s", json.dumps(transformed_body, indent=2, ensure_ascii=False))

            # TODO THIS DOESN"T WORK YET.  NEED TO DEBUG WHY.
            if (
                __metadata__.get("function_calling") != "native"
                and transformed_body["model"] in FEATURE_SUPPORT["function_calling"]
            ):
                await self._enable_native_function_support(
                    transformed_body["model"], __metadata__
                )

            ############################## MAIN LOOP STARTS HERE ##############################
            # 1. If stream, we will yield partial responses to the UI as they arrive.
            # 2. If not streaming, we will generate a single response and return it.
            # 3. If tool calls are pending, we will execute them and continue the loop until no more tool calls are made.
            # 4. Loop until we either run out of tool calls or hit the max loop count
            for loop_count in range(valves.MAX_TOOL_CALL_LOOPS):
                self.log.debug("OpenAI Input payload: %s", json.dumps(transformed_body["input"], indent=2, ensure_ascii=False))

                # Streaming mode: yield partial responses to UI as they arrive
                if transformed_body["stream"]:
                    async for event in self._stream_sse_events(transformed_body, valves.API_KEY, valves.BASE_URL):
                        event_type = event.get("type")
                        self.log.debug("Received SSE event: %s", event_type)

                        # Yield LLM response text as it arrives
                        if event_type == "response.output_text.delta":
                            delta = event.get("delta", "")
                            if delta:
                                final_output.write(delta) # Append to final output. TBD If we use this.
                                yield delta  # Yielding partial text to Open WebUI
                            
                            continue # continue to next event

                        if event_type == "response.reasoning_summary_text.delta":
                            """
                            {
                                "type": "response.reasoning_summary_text.delta",
                                "sequence_number": 4,
                                "item_id": "rs_683cb68e9c288191834748f19371ec6d054ca102265734cd",
                                "output_index": 0,
                                "summary_index": 0,
                                "delta": "**Evalu"
                            }
                            """
                            idx = event.get("summary_index", 0)
                            delta = event.get("delta", "")
                            if delta:
                                # 1) Accumulate for this summary_index
                                reasoning_map[idx] = reasoning_map.get(idx, "") + delta

                                # 2) Merge all blocks (sorted), separated by ---
                                all_text = "\n\n --- \n\n".join(reasoning_map[i] for i in sorted(reasoning_map))

                                # 3) Extract latest title, else fallback to 'Thinking...'
                                matches = re.findall(r"\*\*(.+?)\*\*", all_text, flags=re.DOTALL)
                                latest_title = matches[-1].strip() if matches else "Thinking..."

                                # 4) Build a minimal snippet (omit type="reasoning")
                                snippet = (
                                    f"<details type=\"{__name__}.reasoning\" done=\"false\">\n"
                                    f"<summary>🧠{latest_title}</summary>\n"
                                    f"{all_text}\n"
                                    "</details>"
                                )

                                # 5) Emit to the front end
                                await __event_emitter__({
                                    "type": "chat:completion",
                                    "data": {"content": snippet},
                                })

                            continue

                        # ─── when a tool STARTS ──────────────────────────────────────────────
                        if event_type == "response.output_item.added":
                            item = event.get("item", {})
                            item_type = item.get("type", "")

                            #write item to log for debugging
                            self.log.debug("output_item.added event received: %s", json.dumps(item, indent=2, ensure_ascii=False))

                            if __event_emitter__:
                                started = {
                                    "web_search_call": [
                                        "🔍 Hmm, let me quickly check online…",
                                        "🔍 One sec—looking that up…",
                                        "🔍 Just a moment, searching the web…",
                                    ],
                                    "function_call": [                       # {fn} will be replaced
                                        "🛠️ Running the {fn} tool…",
                                        "🛠️ Let me try {fn}…",
                                        "🛠️ Calling {fn} real quick…",
                                    ],
                                    "file_search_call": [
                                        "📂 Let me skim those files…",
                                        "📂 One sec, scanning the documents…",
                                        "📂 Checking the files right now…",
                                    ],
                                    "image_generation_call": [
                                        "🎨 Let me create that image…",
                                        "🎨 Give me a moment to sketch…",
                                        "🎨 Working on your picture…",
                                    ],
                                    "local_shell_call": [
                                        "💻 Let me run that command…",
                                        "💻 Hold on, executing locally…",
                                        "💻 Firing up that shell command…",
                                    ]
                                }
                                if item_type in started and __event_emitter__:
                                    template = random.choice(started[item_type])
                                    msg = template.format(fn=item.get("name", "a tool"))
                                    await self._emit_status(__event_emitter__, msg, done=False, hidden=False)

                            continue  # continue to next event

                        # ─── when a tool FINISHES ──────────────────────────────────────────────
                        elif event_type == "response.output_item.done":
                            item = event.get("item", {})
                            item_type = item.get("type", "")
                            
                            if __event_emitter__:
                                finished = {
                                    "web_search_call": [
                                        "🔎 Got it—here's what I found!",
                                        "🔎 All set—found that info!",
                                        "🔎 Okay, done searching!",
                                    ],
                                    "function_call": [
                                        "🛠️ Done—the tool finished!",
                                        "🛠️ Got the results for you!",
                                    ],
                                    "file_search_call": [
                                        "📂 Done checking files!",
                                        "📂 Found what I needed!",
                                        "📂 Got the documents ready!",
                                    ],
                                    "image_generation_call": [
                                        "🎨 Your image is ready!",
                                        "🎨 Picture's finished!",
                                        "🎨 All done—image created!",
                                    ],
                                    "local_shell_call": [
                                        "💻 Command complete!",
                                        "💻 Finished running that!",
                                        "💻 Shell task done!",
                                    ]
                                }
                                if item_type in finished and __event_emitter__:
                                    template = random.choice(finished[item_type])
                                    msg = template.format(fn=item.get("name", "Tool"))
                                    await self._emit_status(__event_emitter__, msg, done=True, hidden=False)

                            if item_type == "reasoning":
                                # Merge all partial reasoning so far
                                all_text = "\n\n --- \n\n".join(reasoning_map[i] for i in sorted(reasoning_map))

                                if all_text:
                                    all_text += "\n\n --- \n\n"
                                    
                                    final_snippet = (
                                        f'<details type=\"{__name__}.reasoning\" done="true">\n'
                                        f"<summary>Done thinking!</summary>\n"
                                        f"{all_text}\n"
                                        "</details>"
                                    )

                                    # append to final_output
                                    final_output.write(final_snippet + "\n")

                                    yield final_snippet
                                else:
                                    await self._emit_status(__event_emitter__, "Done thinking!", done=True, hidden=False)

                            continue  # continue to next event

                        # Capture tools from final output
                        if event_type == "response.completed":
                            self.log.debug("Response completed event received. Processing final output in current loop turn.")
                            # 1) Parse the final response data
                            response_data = event.get("response", {})
                            output_items = response_data.get("output", [])

                            # 2) Add them to the next iteration's input
                            transformed_body["input"].extend(output_items)

                            # 3) Accumulate for final DB save
                            collected_items.extend(output_items)

                            # 4) Filter out function calls that need executing
                            calls_to_execute = [
                                i for i in output_items if i.get("type") == "function_call"
                            ]

                            # 5) Merge usage, update total_usage, etc..
                            response_usage = response_data.get("usage", {})
                            for k, v in response_usage.items():
                                if isinstance(v, dict):
                                    total_usage.setdefault(k, {})
                                    for sk, sv in v.items():
                                        if isinstance(sv, (int, float)):
                                            total_usage[k][sk] = total_usage[k].get(sk, 0) + sv
                                        else:
                                            total_usage[k][sk] = sv  # fallback for non-numeric
                                elif isinstance(v, (int, float)):
                                    total_usage[k] = total_usage.get(k, 0) + v
                                else:
                                    total_usage[k] = v  # fallback for non-numeric


                            # Track additional stats
                            total_usage["turn_count"] = total_usage.get("turn_count", 0) + 1
                            total_usage["function_call_count"] = total_usage.get("function_call_count", 0) + len([
                                item for item in output_items if item.get("type") == "function_call"
                            ])

                            continue # continue to next event

                    self.log.debug("Streaming complete. Finalizing response. Chat ID: %s, Message ID: %s",
                        __metadata__.get("chat_id", "unknown_chat"),
                        __metadata__.get("message_id", "unknown_message"),
                    )

                # Non-streaming mode: generate a synchronous response
                else:
                    self.log.info("Non-streaming mode. Generating a synchronous response.")
                    response_text = await self._non_streaming_response(
                        payload=transformed_body,
                        api_key=valves.API_KEY,
                        base_url=valves.BASE_URL,
                    )
                    yield response_text

                # Process any pending function calls; append their results to input history and continue the loop
                if calls_to_execute:
                    self.log.debug(
                        "Processing %d pending function calls", len(calls_to_execute)
                    )
                    # 1) Create tasks
                    tasks = [
                        (
                            asyncio.sleep(0, result="Tool not found")  # If tool doesn't exist
                            if not (tool := __tools__.get(call["name"]))
                            else tool["callable"](**orjson.loads(call["arguments"]))  # Async tool
                            if inspect.iscoroutinefunction(tool["callable"])
                            else asyncio.to_thread(tool["callable"], **orjson.loads(call["arguments"]))  # Sync tool
                        )
                        for call in calls_to_execute
                    ]

                    # 2) Run tasks concurrently
                    results = await asyncio.gather(*tasks)

                    # Build function_call_output items
                    fc_outputs = [
                        {
                            "type": "function_call_output",
                            "call_id": call_obj["call_id"],
                            "output": str(result),
                        }
                        for call_obj, result in zip(calls_to_execute, results)
                    ]

                    # Add these new outputs to the conversation input (so LLM sees them next iteration)
                    transformed_body["input"].extend(fc_outputs)

                    # Accumulate them in our single list for final DB storage
                    collected_items.extend(fc_outputs)

                    # 4) Clear pending function calls for the next loop iteration
                    calls_to_execute.clear()

                else:
                    self.log.debug("No pending function calls. Exiting loop.")
                    break # LLM response is complete, no further tool calls

            ############################## MAIN LOOP ENDS HERE ##############################

            # If PERSIST_TOOL_RESULTS is enabled, append all collected items (function_call, function_call_output, web_search, image_generation, etc.) to the chat message history
            if collected_items:
                db_items = [item for item in collected_items if item.get("type") != "message"]
                if db_items:
                    add_openai_response_items_to_chat_by_id_and_message_id(
                        chat_id,
                        message_id,
                        db_items,
                        model_id,
                    )

            # If valves is DEBUG or user_valves is as value other than "INHERIT", emit citation with logs
            if valves.LOG_LEVEL == "DEBUG" or user_valves.LOG_LEVEL != "INHERIT":
                if __event_emitter__:
                    logs = logs_by_msg_id.get(session_id, [])
                    if logs:
                        await self._emit_citation(
                            __event_emitter__,
                            "\n".join(logs),
                            valves.LOG_LEVEL.capitalize() + " Logs",
                        )

        except Exception as caught_exception:
            await self._emit_error(__event_emitter__, caught_exception, show_error_message=True, show_error_log_citation=True, done=True)
            
        finally:
            self.log.debug("Cleaning up resources after loop iteration %d", loop_count)

            # Emit final completion event with the full output
            if __event_emitter__:
                await self._emit_completion(
                    __event_emitter__,
                    {
                        "done": True,
                        "content": final_output.getvalue(), # I don't think we need to include content.
                        **({"usage": total_usage} if total_usage else {}),
                    },
                )

            logs_by_msg_id.pop(session_id, None)
            current_session_id.reset(token)
            current_log_level.reset(log_token)

            if __metadata__.get("task") is None:
                return # TODO: Remove this after we have implemented our own custom background helpers.
                asyncio.current_task().cancel() # Workaround to skip remaining Open WebUI’s "background" helpers (title, tags, …). Note: middleware.py catches error, logs it, and performs its own upsert.  TODO find cleaner solution.
                await asyncio.sleep(0)

    # ----------------------------------------------------------------------------------------------------
    #  Helpers (Streaming, Non-streaming, Logging, etc.)
    # ----------------------------------------------------------------------------------------------------
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
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]],
        error_obj: Exception | str,
        *,
        show_error_message: bool = True,
        show_error_log_citation: bool = False,
        done: bool = False,
    ) -> None:
        """
        Logs the error and optionally emits data to the front-end UI.
        If 'citation' is True, also emits the debug logs for the current session_id.
        """
        error_message = str(error_obj)  # If it's an exception, convert to string
        self.log.error("Error: %s", error_message)

        if show_error_message and event_emitter:
            await self._emit_completion(
                event_emitter,
                {"error": {"message": error_message}},
                done=done,
            )

            # 2) Optionally emit the citation with logs
            if show_error_log_citation:
                msg_id = current_session_id.get()
                logs = logs_by_msg_id.get(msg_id, [])
                if logs:
                    await self._emit_citation(
                        event_emitter,
                        "\n".join(logs),
                        "Error Logs",
                    )
                else:
                    self.log.warning(
                        "No debug logs found for session_id %s", msg_id
                    )

    async def _emit_citation(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        document: str | list[str],
        source_name: str,
    ) -> None:
        """Emit a citation event to the UI if an emitter is provided."""
        if event_emitter is None:
            return

        if isinstance(document, list):
            doc_text = "\n".join(document)
        else:
            doc_text = document

        await event_emitter(
            {
                "type": "citation",
                "data": {
                    "document": [doc_text],
                    "metadata": [
                        {
                            "date_accessed": datetime.datetime.now().isoformat(),
                            "source": source_name,
                        }
                    ],
                    "source": {"name": source_name},
                },
            }
        )

    async def _emit_completion(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        data: dict[str, Any],
        *,
        done: bool = False,
    ) -> None:
        """Emit a chat:completion event to the UI if possible."""
        if event_emitter is None:
            return

        await event_emitter({"type": "chat:completion", "data": data, "done": done})

    async def _emit_status(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        description: str,
        *,
        done: bool = False,
        hidden: bool = False,
    ) -> None:
        """Emit a status event to the UI if possible."""
        if event_emitter is None:
            return
        
        await event_emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": hidden},
            }
        )

    async def _emit_notification(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        content: str,
        *,
        level: Literal["info", "success", "warning", "error"] = "info",
    ) -> None:
        """Emit a toast notification event to the UI if possible."""
        if event_emitter is None:
            return

        await event_emitter(
            {"type": "notification", "data": {"type": level, "content": content}}
        )

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
        if metadata.get("function_calling") == "native" or model_id not in FEATURE_SUPPORT["function_calling"]:
            return

        model_info = await asyncio.to_thread(Models.get_model_by_id, model_id)
        if not model_info:
            return

        params = model_info.params.model_copy()
        if params.get("function_calling") != "native":
            params["function_calling"] = "native"
            form = ModelForm(
                id=model_info.id,
                base_model_id=model_info.base_model_id,
                name=model_info.name,
                meta=model_info.meta,
                params=ModelParams(**params),
                access_control=model_info.access_control,
                is_active=model_info.is_active,
            )
            await asyncio.to_thread(Models.update_model_by_id, model_info.id, form)

        metadata["function_calling"] = "native"

    @staticmethod
    def transform_tools_for_responses_api(tools_dict: dict[str, dict]) -> list[dict]:
        """
        Convert the internal 'tools_dict' from get_tools(...) into 
        an array of tool definitions for the OpenAI Responses API.

        NOTE: We rely on __tools__ (server-injected) instead of body["tools"], 
        because __tools__ is always provided, whereas body["tools"] is only set 
        if native function calling is enabled by the user. 
        """
        if not tools_dict:
            return []

        items = []
        for name, data in tools_dict.items():
            spec = data.get("spec", {})
            items.append({
                "type": "function",
                "name": spec.get("name", name),
                "description": spec.get("description", ""),
                "parameters": spec.get("parameters", {}),
                "strict": False # Revisit in future if I can get strict working (or if I should at all)
            })
        return items

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

# ----------------------------------------------------------------------------------------------------
#  Public helpers ─ mirror Chats.* naming style
# ----------------------------------------------------------------------------------------------------
"""
Helpers to persist OpenAI responses safely in Open WebUI DB without impacting other
chat data. This allows us to store function call traces, tool outputs, and other
special items related to messages in a structured way, enabling easy retrieval
and reconstruction of conversations with additional context.

Schema Overview
---------------
Inside each chat document (`chat_model.chat`), we store an `openai_responses_pipe` structure:

    {
      "openai_responses_pipe": {
        "__v": 2,                           # version

        "messages": {
          "<message_id>": {
            "model": "o4-mini",          # stamped once – avoids per-item duplication
            "created_at": 1719922512,    # unix-seconds the root message arrived

            "items": [ /* raw output items in arrival order */ ]
          }
        },
      }
    }

When users or the system perform a function call (or any special action)
related to a message, we append these "response items" to
`openai_responses_pipe.messages[<message_id>]`. Later, when reconstructing
the conversation, these items can be inserted above the respective message
that triggered them. This allows for easy referencing of function calls,
their outputs, or any other extra JSON data in the final conversation flow.
"""

def add_openai_response_items_to_chat_by_id_and_message_id(
    chat_id: str,
    message_id: str,
    items: List[Dict[str, Any]],
    model_id: str,
) -> Optional[ChatModel]:
    """
    Append JSON-serializable items under chat.openai_responses_pipe.messages[message_id].
    Returns the updated ChatModel or None if the chat is not found.
    """
    if not items:
        return Chats.get_chat_by_id(chat_id)  # nothing to add

    chat_model = Chats.get_chat_by_id(chat_id)
    if not chat_model:
        return None

    pipe_root = chat_model.chat.setdefault("openai_responses_pipe", {"__v": 2})
    messages_dict = pipe_root.setdefault("messages", {})

    bucket = messages_dict.setdefault(
        message_id,
        {
            "model": model_id,
            "created_at": int(datetime.datetime.utcnow().timestamp()),
            "items": [],
        },
    )
    bucket.setdefault("model", model_id)
    bucket.setdefault("created_at", int(datetime.datetime.utcnow().timestamp()))
    bucket.setdefault("items", [])
    bucket["items"].extend(items)

    return Chats.update_chat_by_id(chat_id, chat_model.chat)


def get_openai_response_items_by_chat_id_and_message_id(
    chat_id: str,
    message_id: str,
    *,
    type_filter: Optional[str] = None,
    model_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return stored items from chat.openai_responses_pipe.messages[message_id].
    If type_filter is given, only items whose 'type' matches are returned.
    """
    chat_model = Chats.get_chat_by_id(chat_id)
    if not chat_model:
        return []

    bucket = (
        chat_model.chat
        .get("openai_responses_pipe", {})
        .get("messages", {})
        .get(message_id, {})
    )

    if model_id and bucket.get("model") != model_id:
        return []

    all_items = bucket.get("items", [])
    if not type_filter:
        return all_items
    return [x for x in all_items if x.get("type") == type_filter]

def remove_details_tags_by_type(text: str, removal_types: list[str]) -> str:
    """
    Removes any <details> tag whose type attribute is in `removal_types`.
    Example:
      remove_details_tags_by_type("Hello <details type='reasoning'>stuff</details>", ["reasoning"])
      => "Hello "
    """
    # Safely escape the types in case they have special regex chars
    pattern_types = "|".join(map(re.escape, removal_types))
    # Example pattern: <details type="reasoning">...</details>
    pattern = rf'<details\b[^>]*\btype=["\'](?:{pattern_types})["\'][^>]*>.*?</details>'
    return re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

def build_responses_history_by_chat_id_and_message_id(
    chat_id: str,
    message_id: Optional[str] = None,
    *,
    model_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Reconstructs a chain of messages up to `message_id` (or the currentId)
    and inserts any items from `openai_responses_pipe.messages[<msg-id>]`
    before the corresponding message.

    Returns a list of items the OpenAI Responses API expects:
      [
        {"type": "function_call", ...},
        {"type": "message", "role": "assistant", "content": [...]},
        ...
      ]
    """

    chat_model = Chats.get_chat_by_id(chat_id)
    if not chat_model:
        return []

    chat_data = chat_model.chat
    if not message_id:
        message_id = chat_data.get("history", {}).get("currentId")

    # Gather chain of messages from root → message_id
    hist_dict = chat_data.get("history", {}).get("messages", {})
    chain = get_message_list(hist_dict, message_id)
    if not chain:
        return []

    # Shortcut to any stored extras
    pipe_messages = (
        chat_data
        .get("openai_responses_pipe", {})
        .get("messages", {})
    )

    final: List[Dict[str, Any]] = []

    for msg in chain:
        msg_id = msg["id"]

        # 1) Pipe items (function_call, function_call_output, etc.) go first
        bucket = pipe_messages.get(msg_id, {})
        extras = []
        if bucket and (not model_id or bucket.get("model") == model_id):
            extras = bucket.get("items", [])
        if extras:
            final.extend(extras)

        # 2) Then the main message as type=message
        role = msg.get("role", "assistant")
        raw_content = msg.get("content", "")  # could be str or list

        # Normalize to a list
        if isinstance(raw_content, str):
            raw_content = [raw_content]

        content_blocks = []
        for part in raw_content:
            # If it's a simple string, treat it as text
            if isinstance(part, str):
                text = part.strip()
                if role == "assistant":
                    text = DETAILS_RE.sub("", text).strip()
                if text:
                    content_blocks.append({
                        "type": "input_text" if role == "user" else "output_text",
                        "text": text
                    })
            # If it's a dict, you can detect e.g. images/files/etc.
            elif isinstance(part, dict):
                # Example: handle images
                if part.get("type") in ("image", "input_image"):
                    content_blocks.append({
                        "type": "input_image" if role == "user" else "output_image",
                        "image_url": part.get("url", "")
                    })
                else:
                    # fallback to text
                    text_str = part.get("text") or part.get("content", "")
                    text_str = text_str.strip()
                    if role == "assistant":
                        text_str = remove_details_tags_by_type(text_str, ["reasoning","{__name__}.reasoning"]) # Open WebUI uses reasoning. This function appends the function name to differentiate it.
                    if text_str:
                        content_blocks.append({
                            "type": "input_text" if role == "user" else "output_text",
                            "text": text_str
                        })
            # else: skip unknown parts

        final.append({
            "type": "message",
            "role": role,
            "content": content_blocks
        })

    return final
                  
