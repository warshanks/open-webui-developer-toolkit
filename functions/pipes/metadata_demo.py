"""
title: Metadata Demo
id: metadata_demo
version: 0.1.0
description: Echoes the last user message and stores custom metadata using
    Chats.upsert_message_to_chat_by_id_and_message_id.
"""

from __future__ import annotations

import time

from open_webui.models.chats import Chats


class Pipe:
    async def pipe(self, body: dict, __metadata__: dict) -> dict:
        """Store custom fields then return them.

        Parameters
        ----------
        body:
            Raw chat payload.
        __metadata__:
            Contains `chat_id` and `message_id` for this message.
        """
        chat_id = __metadata__.get("chat_id")
        message_id = __metadata__.get("message_id")
        user_msg = body["messages"][-1]["content"]

        # Persist a custom flag and timestamp alongside the reply
        custom_data = {
            "role": "assistant",
            "content": f"Echo: {user_msg}",
            "processed_at": int(time.time()),
            "custom_flag": True,
        }
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id,
            message_id,
            custom_data,
        )

        # Fetch the stored message to demonstrate retrieval
        stored = Chats.get_message_by_id_and_message_id(chat_id, message_id)
        return {
            "content": stored.get("content"),
            "processed_at": stored.get("processed_at"),
            "custom_flag": stored.get("custom_flag"),
        }
