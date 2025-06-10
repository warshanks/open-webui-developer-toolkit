"""
title: Reason
id: reason_filter
description: Think before responding.
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.10
version: 0.2.0
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        MODEL: str = "o4-mini"
        REASONING_EFFORT: Literal["low", "medium", "high", "not set"] = "not set"

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True

    async def inlet(self, body: dict) -> dict:
        body["model"] = self.valves.MODEL
        effort = self.valves.REASONING_EFFORT
        if effort != "not set":
            body["reasoning_effort"] = effort
        return body

    async def outlet(self, body: dict) -> dict:
        # TODO: Figure out how to update the UI / model in DB so user can see that it used a different model.
        return body
