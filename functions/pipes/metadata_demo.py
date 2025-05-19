"""
title: Metadata Upsert Demo
id: metadata_demo
version: 1.0.1
description: |
  Quickly demonstrates how to persist custom metadata on existing chat messages **without modifying the message content**.

  ### Why is this helpful?
  You can use this approach to store and retrieve structured tool outputs (like API responses) within the chat history without altering the conversational flow. This enables:

  - Caching expensive or rate-limited tool results in the chat message thread for reuse.
  - Keeping detailed tool data hidden from the user but accessible for future interactions.
"""

from __future__ import annotations

import json
import time
from typing import Dict, Any

from open_webui.models.chats import Chats


class Pipe:
    """Small pipe that patches metadata on a message to illustrate the concept."""

    async def pipe(self, body: Dict[str, Any], __metadata__: Dict[str, Any]):
        chat_id = __metadata__.get("chat_id")
        message_id = __metadata__.get("message_id")
        user_msg = body["messages"][-1]["content"]

        # ------------------------------------------------------------------
        # 1) Upsert WITH a `content` field – text is overwritten
        # ------------------------------------------------------------------
        with_content = {
            "role": "assistant",
            "content": "Example simulated LLM response.",
        }
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id, message_id, with_content
        )
        stored_with = Chats.get_message_by_id_and_message_id(chat_id, message_id)

        # ------------------------------------------------------------------
        # 2) Pretend this dict is a heavy tool result we want to cache
        # ------------------------------------------------------------------

        # Upsert AGAIN – *without* `content` – to attach the tool result
        metadata_only = {
            "custom_flag": True,
            "custom_tool_result_field": {
                "temperature_c": 21,
                "condition": "Partly Cloudy",
            },
        }
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id, message_id, metadata_only
        )
        stored_without = Chats.get_message_by_id_and_message_id(chat_id, message_id)

        # ------------------------------------------------------------------
        # Stream JSON snapshots so the effect is visible in‑chat
        # ------------------------------------------------------------------
        result = (
            "### After upsert WITH content\n```json\n"
            + json.dumps(stored_with, indent=4)
            + "\n```\n\n"
            + "### After upsert WITHOUT content (metadata‑only)\n```json\n"
            + json.dumps(stored_without, indent=4)
            + "\n```"
        )
        yield result
