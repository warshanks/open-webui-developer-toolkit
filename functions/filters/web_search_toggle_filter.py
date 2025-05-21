"""
title: Web Search Toggle Filter
id: web_search_toggle
description: Enable GPT-4o Search Preview when the Web Search toggle is active.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


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
        __event_emitter__: Optional[callable] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Modify the request body when the toggle is active."""

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

        body["model"] = "gpt-4o-search-preview"

        metadata = __metadata__ or {}
        timezone = metadata.get("variables", {}).get(
            "{{CURRENT_TIMEZONE}}", "America/Vancouver"
        )

        body["web_search_options"] = {
            "user_location": {
                "type": "approximate",
                "approximate": {"country": "CA", "timezone": timezone},
            },
            "search_context_size": self.valves.SEARCH_CONTEXT_SIZE.lower(),
        }

        return body

    async def outlet(self, body: dict, __event_emitter__=None) -> dict:

        # PLEASE IMPLEMENT THIS POST PROCESSING

        """
        The outlet should retrieve the last message from body.get("messages", []) and extract all the URLs that end with ?utm_source=openai.  It should then emitt citations for each and emitt a status message with "✅ Web search complete — {citation_count} source{'s' if citation_count != 1 else ''} cited.".  If it didn't find any it should emitt a status of "Search not used — answer based on model's internal knowledge."

        """

        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "",
                    "done": True,
                    "hidden": False,
                },
            }
        )

        return body
