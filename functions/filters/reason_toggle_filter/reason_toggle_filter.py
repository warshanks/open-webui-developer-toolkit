"""
title: Reason
id: reason_filter
description: Think before responding.
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.10
version: 0.3.1
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
from open_webui.models.models import Models
from open_webui.models.chats import Chats


class Filter:
    class Valves(BaseModel):
        MODEL: str = "o4-mini"
        REASONING_EFFORT: Literal["low", "medium", "high", "not set"] = "not set"

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        self.icon = "data:image/svg+xml;base64,PHN2ZyBmaWxsPSJub25lIiB2aWV3Qm94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgY2xhc3M9ImgtWzE4cHldIHctWzE4cHldIj48cGF0aCBkPSJtMTIgM2MtMy41ODUgMC02LjUgMi45MjI1LTYuNSA2LjUzODUgMCAyLjI4MjYgMS4xNjIgNC4yOTEzIDIuOTI0OCA1LjQ2MTVoNy4xNTA0YzEuNzYyOC0xLjE3MDIgMi45MjQ4LTMuMTc4OSAyLjkyNDgtNS40NjE1IDAtMy42MTU5LTIuOTE1LTYuNTM4NS02LjUtNi41Mzg1em0yLjg2NTMgMTRoLTUuNzMwNnYxaDUuNzMwNnYtMXptLTEuMTMyOSAzSC03LjQ2NDhjMC4zNDU4IDAuNTk3OCAwLjk5MjEgMSAxLjczMjQgMXMxLjM4NjYtMC40MDIyIDEuNzMyNC0xem0tNS42MDY0IDBjMC40NDQwMyAxLjcyNTIgMi4wMTAxIDMgMy44NzQgM3MzLjQzLTEuMjc0OCAzLjg3NC0zYzAuNTQ4My0wLjAwNDcgMC45OTEzLTAuNDUwNiAwLjk5MTMtMXYtMi40NTkzYzIuMTk2OS0xLjU0MzEgMy42MzQ3LTQuMTA0NSAzLjYzNDctNy4wMDIyIDAtNC43MTA4LTMuODAwOC04LjUzODUtOC41LTguNTM4NS00LjY5OTIgMC04LjUgMy44Mjc2LTguNSA4LjUzODUgMCAyLjg5NzcgMS40Mzc4IDUuNDU5MSAzLjYzNDcgNy4wMDIydjIuNDU5M2MwIDAuNTQ5NCAwLjQ0MzAxIDAuOTk1MyAwLjk5MTI4IDF6IiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGZpbGw9ImN1cnJlbnRDb2xvciIgZmlsbC1ydWxlPSJldmVub2RkIj48L3BhdGg+PC9zdmc+"

    async def inlet(
        self,
        body: dict,
        __metadata__: dict | None = None,
        ) -> dict:
        body["model"] = self.valves.MODEL
        effort = self.valves.REASONING_EFFORT
        if effort != "not set":
            body["reasoning_effort"] = effort

        self.model_info = Models.get_model_by_id(self.valves.MODEL)

        if __metadata__ and self.model_info:
            __metadata__["model"] = self.model_info.model_dump()

        chat_id = (__metadata__ or {}).get("chat_id")
        message_id = (__metadata__ or {}).get("message_id")

        if chat_id and message_id:
            Chats.upsert_message_to_chat_by_id_and_message_id(
                    chat_id,
                    message_id,
                    {"model": self.valves.MODEL},
                )

        return body

    async def outlet(
        self,
        body: dict,
        __metadata__: dict | None = None,
    ) -> dict:
        """Persist the rerouted model so the UI reflects it."""

        chat_id = (__metadata__ or {}).get("chat_id")
        message_id = (__metadata__ or {}).get("message_id")

        if chat_id and message_id:
            Chats.upsert_message_to_chat_by_id_and_message_id(
                    chat_id,
                    message_id,
                    {"model": self.valves.MODEL},
                )

        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                last_msg["model"] = self.valves.MODEL
                last_msg.setdefault("modelName", self.valves.MODEL)

        return body
