"""
title: Event Emitter Example
author: Open-WebUI Docs Team
version: 1.1
license: MIT
description: |
  This tool demonstrates how to use Open WebUI's built-in event system (__event_emitter__ and __event_call__) to communicate with the UI during tool execution:

  __event_emitter__: Sends immediate, non-blocking UI updates:
      • type="status": Updates progress indicators.
      • type="message": Adds messages directly to the chat.
      • type="citation": Attaches collapsible source/reference blocks.
      • type="replace": Dynamically edits the current chat bubble.

  __event_call__: Displays interactive pop-ups and pauses execution until the user responds:
      • type="input": Prompts the user to enter text input.
      • type="confirmation": Asks the user for Yes/No confirmation.
"""

from __future__ import annotations
import asyncio, time
from typing import Awaitable, Callable, Dict

from pydantic import BaseModel, Field

# Runtime injections → helpful aliases
Emitter = Callable[[Dict[str, any]], Awaitable[None]]
Caller = Callable[[Dict[str, any]], Awaitable[any]]


class Tools:
    # UI-visible “settings” pane ────────────────────────────────────
    class Valves(BaseModel):
        units: int = Field(4, description="Fake work-units to process")
        delay: float = Field(0.6, description="Seconds between units")

    def __init__(self):
        self.valves = self.Valves()

    # Public tool method  –  shows every event type in order
    async def playground(
        self,
        units: int = None,
        __event_emitter__: Emitter | None = None,
        __event_call__: Caller | None = None,
    ) -> str:

        async def emit(evt: Dict):  # await emit({...})
            if __event_emitter__:
                await __event_emitter__(evt)

        total = units if isinstance(units, int) and units > 0 else self.valves.units

        # 1) initial chat stub + progress bar
        await emit({"type": "message", "data": {"content": "⏳ *Demo starting…*"}})
        await emit(
            {
                "type": "status",
                "data": {"description": f"🚀 {total} units", "done": False},
            }
        )

        for idx in range(1, total + 1):
            await asyncio.sleep(self.valves.delay)
            await emit(
                {
                    "type": "status",
                    "data": {"description": f"…unit {idx}/{total}", "done": False},
                }
            )

            # Mid-way:  input   →   confirmation
            if idx == total // 2 and __event_call__:
                note = (
                    await __event_call__(
                        {
                            "type": "input",
                            "data": {
                                "title": "Add a note (optional)",
                                "message": "Enter text to inject or leave blank",
                                "placeholder": "my note",
                            },
                        }
                    )
                    or ""
                )

                proceed = await __event_call__(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": "Continue?",
                            "message": f"We’re at {idx}/{total}. Proceed?",
                        },
                    }
                )

                if not proceed:  # user aborted
                    await emit(
                        {
                            "type": "message",
                            "data": {
                                "content": "⚠️ Cancelled by user",
                                "style": "warning",
                            },
                        }
                    )
                    await emit(
                        {
                            "type": "status",
                            "data": {
                                "description": "cancelled",
                                "done": True,
                                "hidden": True,
                            },
                        }
                    )
                    return "User cancelled."
                if note:
                    await emit(
                        {
                            "type": "message",
                            "data": {"content": f"📝 Note saved: {note}"},
                        }
                    )

        # citation + finished bar + in-place bubble edit
        await emit(
            {
                "type": "citation",
                "data": {
                    "document": [f"Demo processed **{total}** units."],
                    "metadata": [
                        {"date_accessed": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
                    ],
                    "source": {
                        "name": "Event Playground Tool",
                        "url": "https://github.com/open-webui/open-webui",
                    },
                },
            }
        )
        await emit(
            {
                "type": "status",
                "data": {
                    "description": "✅ all done!",
                    "done": True,
                    "style": "success",
                },
            }
        )

        final_msg = f"🎉 Completed {total} units successfully."
        await emit({"type": "replace", "data": {"content": final_msg}})
        return final_msg
