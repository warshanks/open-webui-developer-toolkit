"""
title: Message Persistence Probe
id: message_persistence_probe
author: OpenAI Codex
description: Insert a test assistant message into the chat history.
version: 0.1.0
license: MIT
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Awaitable, Callable

from open_webui.models.chats import Chats


class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None,
        __user__: dict[str, Any] | None = None,
        __request__: Any | None = None,
        __files__: list[dict[str, Any]] | None = None,
        __tools__: dict[str, Any] | None = None,
    ) -> str:
        """Insert a placeholder assistant message and return a confirmation."""

        chat_id = __metadata__.get("chat_id")
        parent_id = __metadata__.get("message_id")
        if not chat_id or not parent_id:
            return "No chat context provided"

        new_id = str(uuid.uuid4())
        timestamp = int(time.time() * 1000)
        message = {
            "id": new_id,
            "parentId": parent_id,
            "childrenIds": [],
            "role": "assistant",
            "content": "This is a persistence probe message.",
            "timestamp": timestamp,
        }

        Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, new_id, message)
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id, parent_id, {"childrenIds": [new_id]}
        )

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "update_db": True,
                    "message_id": new_id,
                    "event": {"content": "probe stored"},
                }
            )

        return f"Inserted probe message {new_id}"
