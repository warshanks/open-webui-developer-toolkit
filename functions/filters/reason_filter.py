"""
title: Reason
id: reason_filter
description: Think before responding.
"""

from __future__ import annotations

from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        MODEL: str = "o4-mini"

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True

    async def inlet(self, body: dict) -> dict:
        body["model"] = self.valves.MODEL
        return body

    async def outlet(self, body: dict) -> dict:
        body["selected_model_id"] = self.valves.MODEL
        return body
