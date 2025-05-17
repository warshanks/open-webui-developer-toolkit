"""
title: Universal Example Tool
version: 1.0.0
author: OpenWebUI Toolkit
author_url: https://example.com
license: MIT
description: |
    Demonstrates a wide variety of best practices & features for building tools in Open WebUI.
    Includes usage of valves, environment variables, event emitters, confirmations, citations,
    and integration with external APIs (e.g. OpenWeather).
requirements: sympy,requests
"""

from datetime import datetime
from typing import Optional, Callable, Awaitable, Any, Dict
import os

import requests
import sympy as sp
from pydantic import BaseModel, Field


class Tools:
    """Showcases key patterns for building Open WebUI tools."""

    class Valves(BaseModel):
        openweather_api_key: str = Field(
            default="",
            description="Optional OpenWeather API key (if empty, will check environment var).",
        )
        default_city: str = Field(
            default="New York",
            description="Fallback city if none is provided to the weather method.",
        )
        citation_demo_enabled: bool = Field(
            default=True,
            description="If True, demo_citation emits a sample citation event.",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.citation = False  # disable built-in citations

    # ------------------------------------------------------------------
    # 1. Simple synchronous method
    # ------------------------------------------------------------------
    def get_current_time(self) -> str:
        """Return the current date/time in human-readable form."""
        now = datetime.now()
        return now.strftime("%A, %B %d, %Y at %I:%M %p")

    # ------------------------------------------------------------------
    # 2. Local computation using SymPy
    # ------------------------------------------------------------------
    def calculate_expression(self, expression: str) -> str:
        """Evaluate a mathematical expression like '2+3' or 'sqrt(16)'."""
        if "=" in expression:
            return "Equations (with '=') are not allowed."
        try:
            val = sp.sympify(expression).evalf()
            text = str(val).rstrip("0").rstrip(".") if "." in str(val) else str(val)
            return f"{expression} = {text}"
        except Exception:
            return "Invalid expression"

    # ------------------------------------------------------------------
    # 3. Read data from the '__user__' object
    # ------------------------------------------------------------------
    def get_user_info(self, __user__: Dict[str, Any] = {}) -> str:
        if not __user__:
            return "No user information provided."
        parts = []
        if "name" in __user__:
            parts.append(f"Name: {__user__['name']}")
        if "email" in __user__:
            parts.append(f"Email: {__user__['email']}")
        if "id" in __user__:
            parts.append(f"ID: {__user__['id']}")
        return " | ".join(parts) if parts else "User fields not found."

    # ------------------------------------------------------------------
    # 4. Async method demonstrating event emitters & confirmations
    # ------------------------------------------------------------------
    async def get_weather(
        self,
        city: str = "",
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
        __event_call__: Optional[Callable[[dict], Awaitable[Any]]] = None,
    ) -> str:
        await _safe_emit_status(__event_emitter__, "Starting weather lookup...", done=False)

        target_city = city or self.valves.default_city

        if __event_call__:
            confirm = await __event_call__({
                "type": "confirmation",
                "data": {
                    "title": "Weather Request",
                    "message": f"Fetch weather for {target_city}?",
                    "confirm_text": "Yes",
                    "cancel_text": "No",
                },
            })
            if not confirm:
                await _safe_emit_status(__event_emitter__, "Request cancelled by user.", done=True)
                return "Cancelled by user."

        api_key = self.valves.openweather_api_key or os.getenv("OPENWEATHER_API_KEY", "")
        if not api_key:
            msg = "Error: No API key set for OpenWeather."
            await _safe_emit_status(__event_emitter__, msg, done=True)
            return msg

        try:
            resp = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": target_city, "appid": api_key, "units": "metric"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            temp = data["main"]["temp"]
            await _safe_emit_status(__event_emitter__, "Weather fetched successfully", done=True)
            return f"Weather in {target_city}: {temp}°C"
        except Exception as e:
            msg = f"Weather fetch failed: {e}"
            await _safe_emit_status(__event_emitter__, msg, done=True)
            return msg

    # ------------------------------------------------------------------
    # 5. Emit a custom citation event
    # ------------------------------------------------------------------
    async def demo_citation(
        self,
        note: str = "A quick example of custom citation usage.",
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        if not self.valves.citation_demo_enabled:
            return "Citation demo is disabled by tool settings."
        if not __event_emitter__:
            return "No event emitter to display citation."
        citation_event = {
            "type": "citation",
            "data": {
                "document": [
                    "Sample text for demonstration of how citations can be appended to the chat."
                ],
                "metadata": [
                    {
                        "date_accessed": datetime.now().isoformat(),
                        "source": "Demo Source Title",
                    }
                ],
                "source": {"name": "Demo Source Title", "url": "https://example.com/demoCitation"},
            },
        }
        await __event_emitter__(citation_event)
        return f"Emitted custom citation event. Additional note: {note}"



async def _safe_emit_status(
    emitter: Optional[Callable[[dict], Awaitable[None]]],
    description: str,
    done: bool,
) -> None:
    """Helper to emit status updates without raising on failure."""
    if not emitter:
        return
    try:
        await emitter({"type": "status", "data": {"description": description, "done": done}})
    except Exception:
        pass
