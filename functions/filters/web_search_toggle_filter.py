"""
title: Search the web
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

        # Expose the toggle in the WebUI (shows a global icon)
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgdmlld0JveD0iMCAwIDMyIDMyIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogIDxwYXRoIGQ9Im0xNi45MDIgMi4zMDRjMC44MTg3LTAuNDI0MTYgMS43ODctMC4yMzI5OCAyLjQwNzIgMC4zODcxNyAwLjYyMDEgMC42MjAxNSAwLjgxMTMgMS41ODg1IDAuMzg3MiAyLjQwNzEtMC43ODY2IDEuNTE4MS0xLjcxOTMgMi44NDc5LTIuODQxNyA0LjA0MzUgMS4xMjg0IDEuNDAzMiAxLjk3NjQgMi44NTY4IDIuMzM0NiA0LjIyNDcgMC40MTc1IDEuNTk0MiAwLjE4MzQgMy4yMDE0LTEuMTk5NCA0LjMwNzctMS4xMTA3IDAuODg4NS0yLjM1ODggMC43Njg2LTMuMzU1NiAwLjM1NjktMC45NzAyLTAuNDAwOC0xLjgzMDctMS4xMTc2LTIuNDIxNC0xLjY4ODEtMC4zNjQxLTAuMzUxNy0wLjM3NDItMC45MzItMC4wMjI0LTEuMjk2MiAwLjM1MTctMC4zNjQxIDAuOTMyLTAuMzc0MiAxLjI5NjEgLTAuMDIyNSAwLjUzMiAwLjUxMzkgMS4xOTUgMS4wNDI3IDEuODQ3NyAxLjMxMjMgMC42MjYxIDAuMjU4NyAxLjEwMDQgMC4yMzM5IDEuNTEwMy0wLjA5NCAwLjY0NjktMC41MTc2IDAuODY3Ny0xLjI3OTQgMC41NzEyLTIuNDExNi0wLjI2MTItMC45OTc0LTAuOTEwOS0yLjE3MzgtMS44ODg1LTMuNDEzMi0wLjUzMjMgMC40NjMtMS4xMDA4IDAuOTA1OC0xLjcwODcgMS4zMzI1LTAuMDI3IDAuMDE5LTAuMDU0NiAwLjAzNjMtMC4wODI4IDAuMDUxOS0wLjA1NjggMC42NjY3LTAuMjgxMSAxLjIzNzEtMC42NzYgMS42OTE4LTAuNDQ5NSAwLjUxNzYtMS4wNDIyIDAuNzk1MS0xLjYwODcgMC45NDk1LTAuOTAzIDAuMjQ2MS0xLjk4MzkgMC4yMzAzLTIuNzcyNiAwLjIxODgtMC4xNTE3OC0wLjAwMjItMC4yOTI3NC0wLjAwNDMtMC40MTk1My0wLjAwNDMtMC41MDYyNiAwLTAuOTE2NjYtMC40MTA0LTAuOTE2NjYtMC45MTY2IDAtMC4xMjY4LTAuMDAyMDYtMC4yNjc4LTAuMDA0MjctMC40MTk1LTAuMDExNDktMC43ODg3LTAuMDI3MjUtMS44Njk2IDAuMjE4ODUtMi43NzI2IDAuMTU0MzktMC41NjY1MSAwLjQzMTg1LTEuMTU5MyAwLjk0OTQ1LTEuNjA4OCAwLjQ1NDY4LTAuMzk0ODcgMS4wMjUyLTAuNjE5MTQgMS42OTE5LTAuNjc1OTcgMC4wMTU2LTAuMDI4MTggMC4wMzI5LTAuMDU1ODMgMC4wNTE4LTAuMDgyOCAwLjM2NDQtMC41MTkxMSAwLjc0MDYtMS4wOTUgMS4xMzA5LTEuNDczMS0yLjY0OTYtMS40NTQzLTUuMTk3NS0xLjMzNTQtNi41MTktMC4wMTM4Ny0wLjg4NzExIDAuODg3MTEtMS4yMzc1IDIuMjg3NS0wLjkyMjgzIDMuOTY1NiAwLjMxMzY2IDEuNjcyOCAxLjI4MDUgMy41MjIgMi44Njc0IDUuMTA4OSAwLjkzNjg2IDAuOTM2OSAxLjk0OTEgMS41OTExIDIuNzc3MSAyLjAwOTEgMC40MTM1NCAwLjIwODggMC43NzM1OSAwLjM1NDggMS4wNDU3IDAuNDQ2NSAwLjIwMzcgMC4wNjg2IDAuMzIwNSAwLjA5MzkgMC4zNjM0IDAuMTAzMiAwLjAyMjYgMC4wMDQ5IDAuMDI0NiAwLjAwNTMgMC4wMDc4IDAuMDA1MyAwLjUwNjMgMCAwLjkxNjcgMC40MTA0IDAuOTE2NyAwLjkxNjdzLTAuNDEwNCAwLjkxNjctMC45MTY3IDAuOTE2NmMtMC4yNzc2IDAtMC42MzUtMC4wOTYxLTAuOTU2NC0wLjIwNDQtMC4zNjA4OC0wLjEyMTYtMC44MDEzLTAuMzAyMi0xLjI4NjctMC41NDczLTAuOTY5OS0wLjQ4OTYtMi4xNDk2LTEuMjUxNy0zLjI0NzMtMi4zNDkzLTEuODE0LTEuODE0LTIuOTgyOC0zLjk4NjgtMy4zNzI5LTYuMDY3NS0wLjM4OTE1LTIuMDc1NC0wLjAxMTM3LTQuMTYgMS40Mjg0LTUuNTk5OCAyLjI0ODktMi4yNDkgNS45Nzk1LTEuOTIyIDkuMDk5NzUtMC4wNjY0OSAxLjI0NTgtMS4yMDU5IDIuNjM3Ni0yLjE5ODIgNC4yMzg5LTMuMDI3OXptLTQuNzQ5IDYuMzc3NGMwLjQ4MjcgMC4yODAzNiAwLjg4NTYgMC42ODMxNyAxLjE2NTkgMS4xNjU5IDIuMDc1NC0xLjU2MzEgMy41ODUzLTMuMzQ1MiA0Ljc0OTYtNS41OTI1IDAuMDM2Mi0wLjA2OTgyIDAuMDMxNy0wLjE3OTk1LTAuMDU1Ny0wLjI2NzM3LTAuMDg3NC0wLjA4NzQxLTAuMTk3NS0wLjA5MTg5LTAuMjY3NC0wLjA1NTcyLTIuMjQ3MiAxLjE2NDQtNC4wMjkzIDIuNjc0My01LjU5MjQgNC43NDk2em0tMi45ODQ3IDQuMTUwN2MwLjY1NDYyIDAuMDAzNCAxLjI3MjUtMC4wMTM1IDEuODAwNy0wLjE1NzUgMC4zNTU5LTAuMDk3IDAuNTc1LTAuMjMxMSAwLjcwNjYtMC4zODI3IDAuMTE5Mi0wLjEzNzMgMC4yNDEzLTAuMzczNiAwLjI0MTMtMC44Mzc4IDAtMC43NTctMC42MTM2LTEuMzcwNy0xLjM3MDYtMS4zNzA3LTAuNDY0MiAwLTAuNzAwNTggMC4xMjIxLTAuODM3ODQgMC4yNDEzLTAuMTUxNiAwLjEzMTctMC4yODU3NSAwLjM1MDctMC4zODI3NiAwLjcwNjYtMC4xNDM5NSAwLjUyODMtMC4xNjA4OCAxLjE0NjEtMC4xNTc0MiAxLjgwMDh6Ii8+Cjwvc3ZnPg=="
        )

    def _add_web_search_tool(self, body: dict) -> None:
        """Append the web_search tool to ``body['tools']`` if missing."""

        entry = {
            "type": "web_search",
            "search_context_size": self.valves.SEARCH_CONTEXT_SIZE,
        }

        tools = body.setdefault("tools", [])
        if not any(t.get("type") == "web_search" for t in tools):
            tools.append(entry)

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

            # Set up reroute: override model and inject search options
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
            self._add_web_search_tool(body)

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
