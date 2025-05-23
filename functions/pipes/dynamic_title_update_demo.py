"""
title: Dynamic Title Update Demo
id: dynamic_title_update_demo
author: Codex
version: 0.1.0
license: MIT
description: Example pipe that updates a chat title while running.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from open_webui.models.chats import Chats


class Pipe:
    """Pipeline demonstrating manual chat title updates."""

    async def pipe(
        self,
        body: Dict[str, Any],
        __metadata__: Dict[str, Any],
        __request__: Any,
    ):
        chat_id = __metadata__.get("chat_id")
        if not chat_id:
            yield "Missing chat_id"
            return

        config = __request__.app.state.config
        old_setting = getattr(config, "ENABLE_TITLE_GENERATION", True)
        config.ENABLE_TITLE_GENERATION = False
        try:
            Chats.update_chat_title_by_id(chat_id, "Processing...")
            yield "starting"

            await asyncio.sleep(0)

            Chats.update_chat_title_by_id(chat_id, "Halfway done")
            yield "halfway"

            await asyncio.sleep(0)

            final_title = f"Completed: {body['messages'][-1]['content']}"
            Chats.update_chat_title_by_id(chat_id, final_title)
            yield "done"
        finally:
            config.ENABLE_TITLE_GENERATION = old_setting
