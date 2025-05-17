"""
title: Stream Logging Filter
id: stream_logging_filter
description: Demonstrates the optional ``stream`` hook for filters.
author: open-webui
license: MIT
version: 0.0.0
"""

from typing import Any, Awaitable, Callable
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(0, description="Execution priority")

    def __init__(self) -> None:
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        print("[stream_logging] inlet:", body)
        return body

    async def stream(self, event: dict[str, Any]) -> dict[str, Any]:
        print("[stream_logging] event:", event.get("type"))
        return event

    async def outlet(
        self,
        body: dict,
        __event_emitter__: Callable[[dict], Awaitable[None]],
    ) -> dict:
        print("[stream_logging] outlet:", body)
        return body
