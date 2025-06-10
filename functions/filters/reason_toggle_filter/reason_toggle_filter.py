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


class Filter:
    class Valves(BaseModel):
        MODEL: str = "o4-mini"
        REASONING_EFFORT: Literal["low", "medium", "high", "not set"] = "not set"

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,PHN2ZyBmaWxsPSJub25lIiB2aWV3Qm94PSIwIDAgMjQgMjQi"
            "IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgY2xhc3M9ImgtWzE4cHldIHctWzE4"
            "cHldIj48cGF0aCBkPSJtMTIgM2MtMy41ODUgMC02LjUgMi45MjI1LTYuNSA2LjUzODUgMCAyLjI4"
            "MjYgMS4xNjIgNC4yOTEzIDIuOTI0OCA1LjQ2MTVoNy4xNTA0YzEuNzYyOC0xLjE3MDIgMi45MjQ4"
            "LTMuMTc4OSAyLjkyNDgtNS40NjE1IDAtMy42MTU5LTIuOTE1LTYuNTM4NS02LjUtNi41Mzg1em0y"
            "Ljg2NTMgMTRoLTUuNzMwNnYxaDUuNzMwNnYtMXptLTEuMTMyOSAzSC03LjQ2NDhjMC4zNDU4IDAu"
            "NTk3OCAwLjk5MjEgMSAxLjczMjQgMXMxLjM4NjYtMC40MDIyIDEuNzMyNC0xem0tNS42MDY0IDBj"
            "MC40NDQwMyAxLjcyNTIgMi4wMTAxIDMgMy44NzQgM3MzLjQzLTEuMjc0OCAzLjg3NC0zYzAuNTQ4"
            "My0wLjAwNDcgMC45OTEzLTAuNDUwNiAwLjk5MTMtMXYtMi40NTkzYzIuMTk2OS0xLjU0MzEgMy42"
            "MzQ3LTQuMTA0NSAzLjYzNDctNy4wMDIyIDAtNC43MTA4LTMuODAwOC04LjUzODUtOC41LTguNTM4"
            "NS00LjY5OTIgMC04LjUgMy44Mjc2LTguNSA4LjUzODUgMCAyLjg5NzcgMS40Mzc4IDUuNDU5MSAz"
            "LjYzNDcgNy4wMDIydjIuNDU5M2MwIDAuNTQ5NCAwLjQ0MzAxIDAuOTk1MyAwLjk5MTI4IDF6IiBj"
            "bGlwLXJ1bGU9ImV2ZW5vZGQiIGZpbGw9ImN1cnJlbnRDb2xvciIgZmlsbC1ydWxlPSJldmVub2Rk"
            "Ij48L3BhdGg+PC9zdmc+"
        )


    async def inlet(
        self,
        body: dict,
        __metadata__: dict | None = None,
    ) -> dict:
        body["model"] = self.valves.MODEL
        if self.valves.REASONING_EFFORT != "not set":
            body["reasoning_effort"] = self.valves.REASONING_EFFORT

        if __metadata__ is not None:
            try:
                from open_webui.models.models import Models

                __metadata__["model"] = Models.get_model_by_id(
                    self.valves.MODEL
                ).model_dump()
            except Exception:
                pass

        meta = __metadata__ or {}
        self._persist_model(meta.get("chat_id"), meta.get("message_id"))
        return body

    async def outlet(
        self,
        body: dict,
        __metadata__: dict | None = None,
    ) -> dict:
        """Persist the rerouted model so the UI reflects it."""

        meta = __metadata__ or {}
        self._persist_model(meta.get("chat_id"), meta.get("message_id"))

        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                last_msg["model"] = self.valves.MODEL
                last_msg.setdefault("modelName", self.valves.MODEL)

        return body

    def _persist_model(self, chat_id: str | None, message_id: str | None) -> None:
        if chat_id and message_id:
            try:
                from open_webui.models.chats import Chats

                Chats.upsert_message_to_chat_by_id_and_message_id(
                    chat_id, message_id, {"model": self.valves.MODEL}
                )
            except Exception:
                pass
