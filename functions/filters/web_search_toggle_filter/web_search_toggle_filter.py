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

        # Disable built-in Open WebUI Search, just to be safe
        if __metadata__:
            __metadata__.setdefault("features", {})
            __metadata__["features"]["web_search"] = False  # Disable built-in Open WebUI Search

        body.tools.append({
                "type": "web_search",
                "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,

                # Temp hardcode until I implement a more elegant way to handle this.
                "user_location": {
                    "type": "approximate",
                    "country": "CA",
                    "city": "Langley",
                    "region": "BC",
                }
            })

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
        pass