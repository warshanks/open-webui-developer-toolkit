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

        # Expose the toggle in the WebUI (shows a magnifying glass icon)
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIg"
            "ZmlsbD0ibm9uZSIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiI+PGNpcmNsZSBj"
            "eD0iMTEiIGN5PSIxMSIgcj0iOCIvPjxsaW5lIHgxPSIyMSIgeTE9IjIxIiB4Mj0iMTYuNjUiIHkyPSIx"
            "Ni42NSIvPjwvc3ZnPg=="
        )

    def _add_web_search_tool(self, body: dict, registry: dict | None = None) -> None:
        """
        Add OpenAI's web_search tool to the request if not already present.
        Optionally also add it to the registry for tool discovery.
        """
        entry = {
            "type": "web_search",
            "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,
        }

        # Ensure 'tools' is a list, append entry if missing
        tools = body.setdefault("tools", [])
        if not any(t.get("type") == "web_search" for t in tools):
            tools.append(entry)

        if registry is not None:
            reg_tools = registry.setdefault("tools", [])
            if not any(t.get("type") == "web_search" for t in reg_tools):
                reg_tools.append(entry)

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Optional[callable] = None,
        __metadata__: Optional[dict] = None,
        __tools__: Optional[dict] = None,
    ) -> dict:
        """
        Main entry point: Modify the request body to enable or route web search.
        - If the selected model supports web_search natively, inject the tool.
        - If not, reroute to the gpt-4o-search-preview model and configure search options.
        """
        body.setdefault("features", {})[
            "web_search"
        ] = False  # Ensure built-in Open-WebUI web search feature is disabled.
        model = body.get("model")

        if model not in WEB_SEARCH_MODELS:
            # Model does NOT natively support web_search.
            # Reroute to gpt-4o-search-preview, and provide search context/options.

            # Optionally notify UI of the reroute action
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "🔍 Web search detected — rerouting to GPT-4o Search Preview...",
                            "done": False,
                            "hidden": False,
                        },
                    }
                )

            # Set up reroute: override model, inject search options, remove tools
            body.update(
                {
                    "model": "gpt-4o-search-preview",
                    "web_search_options": {
                        "user_location": {
                            "type": "approximate",
                            "approximate": {
                                "country": "CA",
                                "timezone": (__metadata__ or {})
                                .get("variables", {})
                                .get("{{CURRENT_TIMEZONE}}", "America/Vancouver"),
                            },
                        },
                        "search_context_size": self.valves.SEARCH_CONTEXT_SIZE.lower(),
                    },
                }
            )
            # Remove 'tools' (if present) as this route does not use them
            if "tools" in body:
                del body["tools"]

        else:
            # Model supports web_search: add the web_search tool if needed
            self._add_web_search_tool(body, __tools__)

        return body

    async def outlet(self, body: dict, __event_emitter__=None) -> dict:
        """
        Post-processing for responses:
        - If not using a native web_search model, emit citation events for any URLs found in the last message.
        - Emit a summary status message for the UI.
        """
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
        """Emit a citation event for a given URL."""
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
        """Emit a status event to the UI (or logs)."""
        if emitter is None:
            return

        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )
