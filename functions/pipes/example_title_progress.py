"""
title: Example Title Progress Pipe
id: example_title_progress
version: 0.1.0
description: Update the chat title multiple times to show task progress.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Callable, Awaitable, Dict
from fastapi import Request

from open_webui.models.chats import Chats


class Pipe:
    async def pipe(
        self,
        body: Dict[str, Any],
        __request__: Request,
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __metadata__: Dict[str, Any],
        **_,
    ) -> AsyncIterator[str]:
        chat_id = __metadata__.get("chat_id")

        # Disable automatic title generation for this request
        original = __request__.app.state.config.ENABLE_TITLE_GENERATION
        __request__.app.state.config.ENABLE_TITLE_GENERATION = False

        try:
            for step in range(1, 4):
                title = f"Processing {step}/3"
                Chats.update_chat_title_by_id(chat_id, title)
                await __event_emitter__({"type": "chat:title", "data": title})
                await asyncio.sleep(0.1)  # simulate work
                yield f"Step {step} complete\n"

            final_title = "Task Complete"
            Chats.update_chat_title_by_id(chat_id, final_title)
            await __event_emitter__({"type": "chat:title", "data": final_title})
            yield "All done!"
        finally:
            __request__.app.state.config.ENABLE_TITLE_GENERATION = original
