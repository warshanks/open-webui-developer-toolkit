"""
title: Web Search
id: web_search_toggle_filter
description: Enable GPT-4o Search Preview when the Web Search toggle is active.
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime
import re
from pydantic import BaseModel

WEB_SEARCH_MODELS = {
    "openai_responses.gpt-4.1",
    "openai_responses.gpt-4.1-mini",
    "openai_responses.gpt-4o",
    "openai_responses.gpt-4o-mini",
}


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

    def _add_web_search_tool(self, body: dict, registry: dict | None = None) -> None:
        """Append the OpenAI web search tool if missing."""
        entry = {
            "type": "web_search",
            "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,
        }

        tools = body.setdefault("tools", [])
        if not any(t.get("type") == "web_search" for t in tools):
            tools.append(entry)

        if registry is not None:
            reg_tools = registry.setdefault("tools", [])
            if not any(t.get("type") == "web_search" for t in reg_tools):
                reg_tools.append(entry)


    def _enable_search_preview(self, body: dict, timezone: str) -> None:
        """Switch the request to GPT-4o Search Preview."""
        body["model"] = "gpt-4o-search-preview"
        body["web_search_options"] = {
            "user_location": {
                "type": "approximate",
                "approximate": {"country": "CA", "timezone": timezone},
            },
            "search_context_size": self.valves.SEARCH_CONTEXT_SIZE.lower(),
        }

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Optional[callable] = None,
        __metadata__: Optional[dict] = None,
        __tools__: Optional[dict] = None,
    ) -> dict:
        """Modify the request body when the toggle is active."""

        model = body.get("model")
        if model in WEB_SEARCH_MODELS:
            self._add_web_search_tool(body, __tools__)

            return body

        features = body.setdefault("features", {})
        # \U0001f9e0 Override native search and explicitly set GPT-4o route
        features["web_search"] = False

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "\ud83d\udd0d Web search detected \u2014 rerouting to GPT-4o Search Preview...",
                        "done": False,
                        "hidden": False,
                    },
                }
            )

        metadata = __metadata__ or {}
        timezone = metadata.get("variables", {}).get(
            "{{CURRENT_TIMEZONE}}", "America/Vancouver"
        )

        self._enable_search_preview(body, timezone)

        self._add_web_search_tool(body, __tools__)

        return body

    async def outlet(self, body: dict, __event_emitter__=None) -> dict:
        """Emit citations from the response and a final status update."""

        model = body.get("model")
        if model not in WEB_SEARCH_MODELS:
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
                await self._emit_citation(__event_emitter__, url)
    
            if urls:
                msg = f"✅ Web search complete — {len(urls)} source{'s' if len(urls) != 1 else ''} cited."
            else:
                msg = "Search not used — answer based on model's internal knowledge."
    
            await self._emit_status(__event_emitter__, msg, done=True)

            return body

        return body

    @staticmethod
    def _extract_urls(text: str) -> list[str]:
        pattern = r"https?://[^\s)]+(?:\?|&)utm_source=openai[^\s)]*"
        matches = re.findall(pattern, text)
        return matches

    @staticmethod
    async def _emit_citation(emitter: callable | None, url: str) -> None:
        if emitter is None:
            return

        cleaned = url.replace("?utm_source=openai", "").replace("&utm_source=openai", "")
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
    async def _emit_status(emitter: callable | None, description: str, *, done: bool = False) -> None:
        if emitter is None:
            return

        await emitter(
            {"type": "status", "data": {"description": description, "done": done, "hidden": False}}
        )
