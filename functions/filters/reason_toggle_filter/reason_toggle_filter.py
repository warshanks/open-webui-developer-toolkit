"""
title: Think
id: reason_filter
description: Think before responding
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.10
version: 0.3.1
"""

from __future__ import annotations
from typing import Any, Awaitable, Callable, Literal
from pydantic import BaseModel, Field

R1_SYSTEM_PROMPT = """
You are an AI assistant that rigorously follows this response protocol:

1. First, conduct a detailed analysis of the question. Consider different angles, potential solutions, and reason through the problem step-by-step. Enclose this entire thinking process within <think> and </think> tags.

2. After the thinking section, provide a clear, concise, and direct answer to the user's question. Separate the answer from the think section with a newline.

Ensure that the thinking process is thorough but remains focused on the query. The final answer should be standalone and not reference the thinking section.
""".strip()

class Filter:
    class Valves(BaseModel):
        REASONING_EFFORT: Literal["minimal", "low", "medium", "high", "not set"] = (
            "high"
        )
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        self.icon = "data:image/svg+xml;base64,PHN2ZyBmaWxsPSJub25lIiB2aWV3Qm94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgY2xhc3M9ImgtWzE4cHldIHctWzE4cHldIj48cGF0aCBkPSJtMTIgM2MtMy41ODUgMC02LjUgMi45MjI1LTYuNSA2LjUzODUgMCAyLjI4MjYgMS4xNjIgNC4yOTEzIDIuOTI0OCA1LjQ2MTVoNy4xNTA0YzEuNzYyOC0xLjE3MDIgMi45MjQ4LTMuMTc4OSAyLjkyNDgtNS40NjE1IDAtMy42MTU5LTIuOTE1LTYuNTM4NS02LjUtNi41Mzg1em0yLjg2NTMgMTRoLTUuNzMwNnYxaDUuNzMwNnYtMXptLTEuMTMyOSAzSC03LjQ2NDhjMC4zNDU4IDAuNTk3OCAwLjk5MjEgMSAxLjczMjQgMXMxLjM4NjYtMC40MDIyIDEuNzMyNC0xem0tNS42MDY0IDBjMC40NDQwMyAxLjcyNTIgMi4wMTAxIDMgMy44NzQgM3MzLjQzLTEuMjc0OCAzLjg3NC0zYzAuNTQ4My0wLjAwNDcgMC45OTEzLTAuNDUwNiAwLjk5MTMtMXYtMi40NTkzYzIuMTk2OS0xLjU0MzEgMy42MzQ3LTQuMTA0NSAzLjYzNDctNy4wMDIyIDAtNC43MTA4LTMuODAwOC04LjUzODUtOC41LTguNTM4NS00LjY5OTIgMC04LjUgMy44Mjc2LTguNSA4LjUzODUgMCAyLjg5NzcgMS40Mzc4IDUuNDU5MSAzLjYzNDcgNy4wMDIydjIuNDU5M2MwIDAuNTQ5NCAwLjQ0MzAxIDAuOTk1MyAwLjk5MTI4IDF6IiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGZpbGw9ImN1cnJlbnRDb2xvciIgZmlsbC1ydWxlPSJldmVub2RkIj48L3BhdGg+PC9zdmc+"

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __metadata__: dict | None = None,
    ) -> dict:
        """
        Inlet: Append R1_SYSTEM_PROMPT to the system prompt of the request.
        """

        messages = body.get("messages", [])

        if isinstance(messages, list):
            if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
                existing_content = messages[0].get("content")

                if isinstance(existing_content, str):
                    messages[0]["content"] = f"{existing_content}\n{R1_SYSTEM_PROMPT}"
                elif isinstance(existing_content, list):
                    appended = False
                    for item in existing_content:
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "text"
                            and isinstance(item.get("text"), str)
                        ):
                            item["text"] = f"{item['text']}\n{R1_SYSTEM_PROMPT}"
                            appended = True
                            break
                    if not appended:
                        existing_content.append({"type": "text", "text": R1_SYSTEM_PROMPT})
                else:
                    messages[0]["content"] = R1_SYSTEM_PROMPT
            else:
                messages.insert(0, {"role": "system", "content": R1_SYSTEM_PROMPT})

            body["messages"] = messages

        return body
