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
"""

import asyncio
import sys
import time
import re
import copy
import json
import base64
import mimetypes
import uuid

from fastapi import Request
from loguru import logger

# Optional: Pydantic for config classes
from pydantic import BaseModel, Field, field_validator
from typing import Any, AsyncGenerator, Awaitable, Callable, Literal

# Optional: Some placeholders for data classes used by Open WebUI
# from open_webui.models.chats import Chats
# from open_webui.models.files import Files
# from open_webui.storage.provider import Storage

# Logging instance for this pipeline
log = logger.bind(auditable=False)

# --------------------------------------------------
#  1. Configuration Classes
# --------------------------------------------------

class Pipe:
    """
    Main pipeline class. Each `Open WebUI` manifold typically has a class named `Pipe`
    that exposes two primary async methods:
      - `pipes()`: returns metadata about available models
      - `pipe()`: runs inference/generation on a single request
    """

    class Valves(BaseModel):
        """
        Top-level plugin settings. 
        (In your original code, these might hold API keys, 
         base URLs, or model name filters, etc.)
        """

        OPENAI_API_KEY: str | None = Field(default=None)
        OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1/")
        # ... Add other global plugin settings here

        LOG_LEVEL: Literal[
            "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
        ] = Field(default="INFO")

        # Example placeholder for toggling streaming
        ENABLE_STREAMING: bool = Field(default=True)

        # Add more as needed...

    class UserValves(BaseModel):
        """
        User-scoped settings. 
        Individual users can override certain plugin settings if you want per-user configs.
        """
        OPENAI_API_KEY: str | None = Field(default=None)
        OPENAI_BASE_URL: str | None = Field(default=None)
        # ... user-specific toggles, like temperature, etc.

        @field_validator("OPENAI_API_KEY")
        @classmethod
        def validate_api_key(cls, v):
            # [Placeholder logic]
            # Possibly ensure the key is well-formed or non-empty
            return v

        # Add more as needed...

    def __init__(self):
        """Initialize default valves."""
        self.valves = self.Valves()
        # Optionally, you could do other startup tasks here

    # --------------------------------------------------
    #  2. Listing/Fetching Available Models
    # --------------------------------------------------

    async def pipes(self) -> list[dict[str, Any]]:
        """
        Returns a list of available model definitions to be exposed in Open WebUI.
        Typically used to show the user a set of selectable models.

        Structure example:
        [
            {
                "id": "openai-gpt-3.5-turbo",
                "name": "GPT-3.5 Turbo",
                "description": "OpenAI's gpt-3.5-turbo model"
            },
            ...
        ]

        If an error occurs, return a special "error" model or handle gracefully.
        """
        # 1. Adjust logging based on valves.LOG_LEVEL, if desired.
        self._update_log_level(self.valves.LOG_LEVEL)

        # 2. Possibly fetch from OpenAI's model list or define them statically.
        #    If you need to call an API, do it here.
        #    (Placeholder: returning some dummy models for the skeleton.)
        try:
            # ... Code to fetch or define your model list
            available_models = [
                {
                    "id": "openai-gpt-3.5-turbo",
                    "name": "GPT-3.5 Turbo",
                    "description": "OpenAI’s turbo model."
                },
                {
                    "id": "openai-gpt-4",
                    "name": "GPT-4",
                    "description": "OpenAI’s GPT-4 model."
                }
            ]
            return available_models
        except Exception as e:
            # Return an "error" model as a fallback
            error_msg = f"Error fetching models: {str(e)}"
            return [{
                "id": "error",
                "name": "OpenAI Model Retrieval Error",
                "description": error_msg
            }]

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
        Called when the user triggers a request to the selected model.
        This method is where you:
          - Parse the request payload
          - Merge user’s custom settings with global settings
          - Call your OpenAI logic
          - Return or stream back the result
        """

        # 1. Merge user-specific settings with the global plugin valves
        merged_valves = self._merge_valves(self.valves, __user__.get("valves"))

        # 2. Possibly create or get an OpenAI client here (HTTPX, etc.)
        #    Something like: self._get_openai_client(merged_valves.OPENAI_API_KEY, ...)

        # 3. Grab model, messages, streaming preference, etc. from `body`
        model_id = body.get("model", "openai-gpt-3.5-turbo")
        user_messages = body.get("messages", [])
        stream_mode = body.get("stream", False)

        # 4. Construct your request payload for the OpenAI API
        #    (System prompt, user messages, etc.)
        #    Example placeholders:
        openai_payload = {
            "model": model_id,
            "messages": user_messages,
            # "temperature": body.get("temperature", 1.0),
            # ...
        }

        # 5. If streaming is requested, you can return an async generator:
        if stream_mode and merged_valves.ENABLE_STREAMING:
            log.info("Streaming mode enabled. Generating an async response stream.")
            return self._streaming_response(openai_payload, __event_emitter__)
        else:
            # Non-streaming response:
            log.info("Non-streaming mode. Generating a synchronous response.")
            response_text = await self._non_streaming_response(openai_payload)
            return response_text

    # --------------------------------------------------
    #  4. Helpers (Streaming, Non-streaming, Logging, etc.)
    # --------------------------------------------------

    async def _streaming_response(
        self,
        payload: dict[str, Any],
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> AsyncGenerator[str, None]:
        """
        Perform streaming call to OpenAI API, yielding text chunks.
        This is a skeleton; fill in the actual logic.
        """

        # [Placeholder: e.g., use httpx or openai's python library streaming approach]
        try:
            # Start the streaming request to the API
            # async for chunk in openai_stream_call(...):
            #     # yield chunk. Possibly parse partial responses.
            #     yield chunk
            yield "This is a placeholder chunk #1..."
            await asyncio.sleep(0.5)
            yield "And this is placeholder chunk #2."

        except Exception as e:
            error_msg = f"Streaming error: {str(e)}"
            # You can optionally signal an error to the front-end
            await self._emit_error(error_msg, event_emitter)
            # Re-raise if you want to fully stop
            raise

    async def _non_streaming_response(self, payload: dict[str, Any]) -> str:
        """
        Perform a one-shot request to the OpenAI API, returning the entire text at once.
        """
        # [Placeholder logic for non-stream call]
        await asyncio.sleep(0.2)  # Pretend we made an API call
        # Example: 
        #   response = openai_api.post(".../completions", json=payload)
        #   return response.get("choices")[0].get("message").get("content")
        return "This is a placeholder non-streamed response from the OpenAI model."

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

    def _merge_valves(self, default_valves: "Pipe.Valves", user_valves_dict: dict[str, Any] | None) -> "Pipe.Valves":
        """
        Merge user-level valves into default. 
        If user_valves is None, returns a copy of default_valves.
        Otherwise, for each field in UserValves with a non-None value, 
        overwrite the default_valves' field.
        """

        if not user_valves_dict:
            return default_valves

        # Convert user_valves_dict to a typed object for validations
        user_valves = self.UserValves(**user_valves_dict)

        # Start with defaults
        merged_data = default_valves.model_dump()

        # Overwrite with non-None user fields
        for field_name in self.UserValves.model_fields:
            user_val = getattr(user_valves, field_name)
            if user_val is not None:
                if field_name in merged_data:
                    merged_data[field_name] = user_val

        # Return new Valves instance
        return self.Valves(**merged_data)

    def _update_log_level(self, level_name: str) -> None:
        """
        Adjust pipeline-specific logging based on level_name. 
        If you want a separate log handler, insert it here. 
        """

        # Validate level exists
        valid_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        if level_name not in valid_levels:
            log.warning(f"Invalid log level requested: {level_name}, defaulting to INFO.")
            level_name = "INFO"

        # If you want to remove old handler and add a new one, do so here.
        # Or simply do:
        logger.remove()  # Remove existing
        logger.add(sys.stdout, level=level_name)

        log.debug(f"Log level updated to {level_name}.")