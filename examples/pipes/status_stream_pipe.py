"""
title: Status Stream Pipe
id: status_stream_pipe
description: Streams words with status events to demonstrate event emitters.
author: open-webui
license: MIT
version: 0.0.0
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable
from pydantic import BaseModel, Field
from fastapi import Request


class Pipe:
    class Valves(BaseModel):
        DELAY: float = Field(0.1, description="Delay between tokens in seconds")

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict,
        __request__: Request,
        __event_emitter__: Callable[[dict], Awaitable[None]],
        __event_call__: Callable[[dict[str, Any]], Awaitable[Any]],
        __task__: str,
        __task_body__: dict[str, Any],
        __files__: list[dict[str, Any]],
        __metadata__: dict[str, Any],
        __tools__: list[Any],
    ) -> AsyncGenerator[str, None]:
        text = body.get("prompt", "Hello world").split()
        for idx, word in enumerate(text, 1):
            await __event_emitter__({"type": "status", "data": {"description": f"Token {idx}", "done": False}})
            yield word + " "
            await asyncio.sleep(self.valves.DELAY)
        await __event_emitter__({"type": "status", "data": {"description": "Complete", "done": True}})
        return
