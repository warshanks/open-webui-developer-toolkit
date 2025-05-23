"""
title: Create an Image
id: create_image_filter
description: Injects the image_generation tool with configurable size and quality.
"""

from __future__ import annotations

from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        SIZE: str = "auto"
        QUALITY: str = "auto"

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgdmlld0JveD0iMCAwIDI0IDI0IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj4KICA8cmVjdCB4PSIzIiB5PSIzIiB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHJ4PSIyIi8+CiAgPGNpcmNsZSBjeD0iOC41IiBjeT0iOC41IiByPSIxLjUiLz4KICA8cGF0aCBkPSJNMyAxOC4wMDNMOC41IDEybDMuNSAzLjUgNC01IDUgNSIvPgo8L3N2Zz4="
        )

    def _add_image_generation_tool(self, body: dict) -> None:
        entry = {
            "type": "image_generation",
            "size": self.valves.SIZE,
            "quality": self.valves.QUALITY,
        }
        tools = body.setdefault("tools", [])
        if not any(t.get("type") == "image_generation" for t in tools):
            tools.append(entry)

    async def inlet(self, body: dict, **_kwargs) -> dict:
        self._add_image_generation_tool(body)
        return body
