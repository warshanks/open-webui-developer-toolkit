"""
title: Multi-Message Bubble Example
id: multi_message_bubble_example
description: Proof-of-concept pipe that replies with two assistant messages in a single turn.
version: 0.1.0
license: MIT
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncGenerator, Awaitable, Callable

from open_webui.models.chats import Chats
try:  # pragma: no cover - open_webui may not be available during tests
    from open_webui.socket.main import get_event_emitter
except Exception:  # noqa: PERF203
    async def _noop(_event: dict[str, Any]) -> None:
        return None

    def get_event_emitter(*_args: Any, **_kwargs: Any) -> Callable[[dict[str, Any]], Awaitable[None]]:
        return _noop


async def _add_assistant_row(
    chat_id: str,
    parent_id: str,
    model_id: str,
    user_id: str,
    session_id: str | None,
) -> str:
    """Create a blank assistant message row and notify the UI."""

    msg_id = str(uuid.uuid4())
    now = int(time.time())

    Chats.upsert_message_to_chat_by_id_and_message_id(
        chat_id,
        msg_id,
        {
            "role": "assistant",
            "parentId": parent_id,
            "childrenIds": [],
            "content": "",
            "model": model_id,
            "timestamp": now,
            "done": False,
        },
    )
    Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, parent_id, {"childrenIds": [msg_id]})

    emitter = get_event_emitter(
        {
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": msg_id,
            "session_id": session_id,
        },
        update_db=False,
    )

    await emitter(
        {
            "type": "chat:message",
            "data": {"chat_id": chat_id, "message_id": msg_id, "content": ""},
        }
    )

    return msg_id


class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __event_call__: Callable[[dict[str, Any]], Awaitable[None]],
        __metadata__: dict[str, Any],
        *_,
    ) -> AsyncGenerator[str, None]:
        """Emit two assistant bubbles in sequence."""

        # Bubble #1 using the provided emitter
        await __event_emitter__(
            {"type": "message", "data": {"content": "👋 Hi! Bubble #1 streaming...\n"}}
        )
        await asyncio.sleep(0.5)
        await __event_emitter__({"type": "status", "data": {"done": True}})

        chat_id = __metadata__["chat_id"]
        parent_id = __metadata__["message_id"]
        model_id = __metadata__["model_id"]
        user_id = __metadata__["user_id"]
        session_id = __metadata__.get("session_id")

        # Bubble #2 with a fresh row and emitter
        second_msg_id = await _add_assistant_row(
            chat_id, parent_id, model_id, user_id, session_id
        )
        emitter2 = get_event_emitter(
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "message_id": second_msg_id,
                "session_id": session_id,
            }
        )

        await emitter2({"type": "message", "data": {"content": "✅ This is bubble #2.\n"}})
        await emitter2({"type": "status", "data": {"done": True}})

        yield ""
