"""
 title: Example Metadata Persistence
 id: example_metadata_persistence
 version: 0.1.0
 description: Demonstrates storing custom metadata in chat history and reading it back on the next turn.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict

from open_webui.models.chats import Chats


class Pipe:
    async def pipe(
        self,
        body: Dict[str, Any],
        __metadata__: Dict[str, Any],
        **_,
    ) -> AsyncIterator[str]:
        chat_id = __metadata__.get("chat_id")
        message_id = __metadata__.get("message_id")

        messages = body.get("messages", [])
        prev_meta = None
        if len(messages) >= 2:
            prev_msg_id = messages[-2].get("id")
            if prev_msg_id:
                prev = Chats.get_message_by_id_and_message_id(chat_id, prev_msg_id)
                prev_meta = prev.get("custom_meta")

        if prev_meta:
            yield f"Previous meta: {prev_meta}\n"
        else:
            yield "No previous meta\n"

        user_text = messages[-1].get("content", "")
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id,
            message_id,
            {"custom_meta": f"stored:{user_text}"},
        )
        yield f"Echo: {user_text}"
