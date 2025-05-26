"""
 title: Example Metadata Persistence
 id: example_metadata_persistence
 version: 0.1.0
 description: Demonstrates storing custom metadata in chat history and reading it back on the next turn.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict

from open_webui.utils.misc import get_message_list

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
        chat = Chats.get_chat_by_id(chat_id)
        if chat:
            history = chat.chat.get("history", {})
            messages_lookup = history.get("messages", {})
            chain = get_message_list(messages_lookup, history.get("currentId")) or []
            if chain:
                # Skip the incoming user message at the end
                for msg in reversed(chain[:-1]):
                    if msg.get("role") == "assistant":
                        prev_meta = msg.get("custom_meta")
                        break

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
