"""
title: Search
id: web_search_toggle_filter
description: Search the web
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.10
version: 0.1.0
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional
from datetime import datetime
import re
from pydantic import BaseModel

# Models that natively support OpenAI's web_search tool
WEB_SEARCH_MODELS = {
    #"openai_responses.gpt-4.1",
    #"openai_responses.gpt-4.1-mini",
    #"openai_responses.gpt-4o",
    #"openai_responses.gpt-4o-mini",
}


class Filter:
    class Valves(BaseModel):
        """Configurable settings for the filter."""

        SEARCH_CONTEXT_SIZE: str = "medium"

    def __init__(self) -> None:
        self.valves = self.Valves()

        # Expose the toggle in the WebUI (shows a global icon)
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj4KICA8Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIvPgogIDxsaW5lIHgxPSIyIiB5MT0iMTIiIHgyPSIyMiIgeTI9IjEyIi8+CiAgPHBhdGggZD0iTTEyIDJhMTUgMTUgMCAwIDEgMCAyMCAxNSAxNSAwIDAgMSAwLTIweiIvPgo8L3N2Zz4="
        )

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Optional[callable] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """
        Main entry point: Modify the request body to enable or route web search.
        - If the selected model supports web_search natively, inject the tool.
        - If not, reroute to the gpt-4o-search-preview model and configure search options.
        """

        # SUBJECT TO CHANGE.
        # This is a temp workaround until I can figure out a more elegant way to handle this.

        # Set web search feature flags in __metadata__ for downstream processing
        if __metadata__:
            __metadata__.setdefault("features", {})
            __metadata__["features"]["web_search"] = False  # Disable built-in Open WebUI Search
            __metadata__["features"]["openai_responses.web_search"] = True  # Enable downstream web_search tool

        body["tool_choice"] = "required"  # Force web_search tool to be used

        # Append to messages to encourage model to use web search
        body.setdefault("messages", [])
        body["messages"].append(
            {
                "role": "developer",
                "content": (
                    "Web Search: Enabled \nPlease answer the question using the web_search tool to find the most up-to-date information."
                ),
            }
        )

        return body

    async def outlet(self, body: dict, __event_emitter__=None) -> dict:
        """
        Post-processing for responses:
        - If not using a native web_search model, emit citation events for any URLs found in the last message.
        - Emit a summary status message for the UI.
        if body.get("model") in WEB_SEARCH_MODELS:
            # Native web_search models handle citations/events themselves
            return body

        # For rerouted models, emit citations for each URL found in the response text
        messages = body.get("messages") or []
        last_msg = messages[-1] if messages else None
        content_blocks = last_msg.get("content") if isinstance(last_msg, dict) else None

        # Flatten content blocks into one text string
        if isinstance(content_blocks, list):
            text = " ".join(
                b.get("text", str(b)) if isinstance(b, dict) else str(b)
                for b in content_blocks
            )
        else:
            text = str(content_blocks or "")

        # Find all openai-attributed URLs in the response
        urls = re.findall(r"https?://[^\s)]+(?:\?|&)utm_source=openai[^\s)]*", text)
        for url in urls:
            await self._emit_citation(__event_emitter__, url)

        # Emit status update to UI based on whether any sources were cited
        msg = (
            f"✅ Web search complete — {len(urls)} source{'s' if len(urls) != 1 else ''} cited."
            if urls
            else "Search not used — answer based on model's internal knowledge."
        )
        await self._emit_status(__event_emitter__, msg, done=True)

        return body

    @staticmethod
    async def _emit_citation(emitter: callable | None, url: str) -> None:

        if emitter is None:
            return

        cleaned = url.replace("?utm_source=openai", "").replace(
            "&utm_source=openai", ""
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
    async def _emit_status(
        emitter: callable | None, description: str, *, done: bool = False
    ) -> None:
        if emitter is None:
            return

        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )

        """