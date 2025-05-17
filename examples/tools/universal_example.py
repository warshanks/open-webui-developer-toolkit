"""
title: Universal Example Tool
version: 1.0.0
author: OpenWebUI Toolkit
license: MIT
requirements: sympy,requests

This example demonstrates a variety of patterns when building Open WebUI
Tools.  It includes:
  * Using Valves for configuration
  * Returning strings and numbers
  * Emitting status updates
  * Prompting the user with a confirmation dialog
  * Making HTTP requests
"""

import os
from datetime import datetime
from typing import Optional, Callable, Awaitable, Any

import requests
from pydantic import BaseModel, Field
import sympy as sp


class Tools:
    class Valves(BaseModel):
        weather_api_key: str = Field(
            default="",
            description="OpenWeatherMap API key for the weather tool",
        )
        default_city: str = Field(
            default="New York",
            description="Default city for the weather tool",
        )

    def __init__(self):
        self.valves = self.Valves()

    # --------------------------------------------------------------
    def get_time(self) -> str:
        """Return the current date and time in human readable form."""
        now = datetime.now()
        return now.strftime("%A %B %d, %Y %I:%M %p")

    # --------------------------------------------------------------
    def calculate(self, expression: str) -> str:
        """Evaluate a mathematical expression using SymPy."""
        if "=" in expression:
            return "Equations are not allowed"
        try:
            val = sp.sympify(expression).evalf()
            return f"{expression} = {val}".rstrip("0").rstrip(".")
        except Exception:
            return "Invalid expression"

    # --------------------------------------------------------------
    async def weather(
        self,
        city: Optional[str] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
        __event_call__: Optional[Callable[[dict], Awaitable[Any]]] = None,
    ) -> str:
        """Fetch the current temperature for a city and demonstrate events."""
        await self._emit_status(
            __event_emitter__, "Fetching weather information…", done=False
        )

        api_key = self.valves.weather_api_key or os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            await self._emit_status(
                __event_emitter__, "No API key set for weather tool", done=True
            )
            return "Weather tool is not configured"

        target_city = city or self.valves.default_city

        # Ask the user for confirmation before calling the API
        if __event_call__:
            confirmed = await __event_call__(
                {
                    "type": "confirmation",
                    "data": {
                        "title": "Confirm",
                        "message": f"Look up weather for {target_city}?",
                    },
                }
            )
            if not confirmed:
                await self._emit_status(
                    __event_emitter__, "Weather request cancelled", done=True
                )
                return "Cancelled"

        url = "https://api.openweathermap.org/data/2.5/weather"
        try:
            resp = requests.get(
                url,
                params={"q": target_city, "units": "metric", "appid": api_key},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            temp = data["main"]["temp"]
            await self._emit_status(
                __event_emitter__, "Weather retrieved", done=True
            )
            return f"Temperature in {target_city}: {temp}°C"
        except Exception as e:
            await self._emit_status(__event_emitter__, f"Error: {e}", done=True)
            return "Failed to fetch weather"

    # --------------------------------------------------------------
    async def _emit_status(
        self,
        emitter: Optional[Callable[[dict], Awaitable[None]]],
        desc: str,
        done: bool,
    ) -> None:
        if not emitter:
            return
        await emitter(
            {"type": "status", "data": {"description": desc, "done": done}}
        )
