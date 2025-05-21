"""
title: Web Search Toggle Filter
id: web_search_toggle
description: Enable GPT-4o Search Preview when the Web Search toggle is active.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel

WEB_SEARCH_MODELS = {
    "openai_responses.gpt-4.1",
    "openai_responses.gpt-4.1-mini",
    "openai_responses.gpt-4o",
    "openai_responses.gpt-4o-mini",
}

WEB_SEARCH_PREVIEW_MODEL = "gpt-4o-search-preview"


class Filter:
    class Valves(BaseModel):
        """Configurable settings for the filter."""

        SEARCH_CONTEXT_SIZE: str = "medium"

    def __init__(self) -> None:
        self.valves = self.Valves()

        # Show a toggle in the UI labelled "Web Search" with a magnifying glass icon
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIg"
            "ZmlsbD0ibm9uZSIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiI+PGNpcmNsZSBj"
            "eD0iMTEiIGN5PSIxMSIgcj0iOCIvPjxsaW5lIHgxPSIyMSIgeTE9IjIxIiB4Mj0iMTYuNjUiIHkyPSIx"
            "Ni42NSIvPjwvc3ZnPg=="
        )

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Update the request based on the selected model."""

        model = body.get("model")
        if model in WEB_SEARCH_MODELS:
            self._add_search_tool(body)
            return body

        await self._configure_search_preview(body, __event_emitter__, __metadata__)
        return body

    async def outlet(self, body: dict, __event_emitter__=None) -> dict:
        """Emit citations from the response and a final status update."""

        if not __event_emitter__:
            return body

        last_msg = (body.get("messages") or [])[-1] if body.get("messages") else None
        content_blocks = last_msg.get("content") if isinstance(last_msg, dict) else None

        if isinstance(content_blocks, list):
            text = " ".join(
                b.get("text", str(b)) if isinstance(b, dict) else str(b)
                for b in content_blocks
            )
        else:
            text = str(content_blocks or "")

        urls = self._extract_urls(text)

        for url in urls:
            await self._send_citation(__event_emitter__, url)

        if urls:
            msg = f"✅ Web search complete — {len(urls)} source{'s' if len(urls) != 1 else ''} cited."
        else:
            msg = "Search not used — answer based on model's internal knowledge."

        await self._send_status(__event_emitter__, msg, done=True)

        return body

    def _add_search_tool(self, body: dict) -> None:
        """Add the OpenAI web search tool if missing."""

        tools = body.setdefault("tools", [])
        if not any(t.get("type") == "web_search" for t in tools):
            tools.append(
                {
                    "type": "web_search",
                    "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,
                }
            )

    async def _configure_search_preview(
        self,
        body: dict,
        emitter: Optional[Callable[[dict], Awaitable[None]]],
        metadata: Optional[dict],
    ) -> None:
        """Configure GPT-4o Search Preview and emit status."""

        features = body.setdefault("features", {})
        # 🧠 Override native search and explicitly set GPT-4o route
        features["web_search"] = False

        if emitter:
            await self._send_status(
                emitter,
                "\ud83d\udd0d Web search detected \u2014 rerouting to GPT-4o Search Preview...",
            )

        body["model"] = WEB_SEARCH_PREVIEW_MODEL

        timezone = (metadata or {}).get("variables", {}).get(
            "{{CURRENT_TIMEZONE}}",
            "America/Vancouver",
        )

        body["web_search_options"] = {
            "user_location": {
                "type": "approximate",
                "approximate": {"country": "CA", "timezone": timezone},
            },
            "search_context_size": self.valves.SEARCH_CONTEXT_SIZE.lower(),
        }

    @staticmethod
    def _extract_urls(text: str) -> list[str]:
        pattern = r"https?://[^\s)]+[?&]utm_source=openai[^\s)]*"
        return re.findall(pattern, text)

    @staticmethod
    async def _send_citation(emitter: Callable[[dict], Awaitable[None]], url: str) -> None:
        cleaned = (
            url.replace("?utm_source=openai", "").replace("&utm_source=openai", "")
        )
        await emitter(
            {
                "type": "citation",
                "data": {
                    "document": [cleaned],
                    "metadata": [
                        {"date_accessed": datetime.now().isoformat(), "source": cleaned}
                    ],
                    "source": {"name": cleaned, "url": cleaned},
                },
            }
        )

    @staticmethod
    async def _send_status(
        emitter: Callable[[dict], Awaitable[None]],
        description: str,
        *,
        done: bool = False,
    ) -> None:
        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )
