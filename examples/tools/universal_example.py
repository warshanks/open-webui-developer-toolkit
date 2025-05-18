"""
title: Event Playground Tool
author: Open-WebUI Docs Team
version: 1.0
license: MIT
description: |
  One 100-line file that shows **every** event channel Open-WebUI supports.
  Read it top-to-bottom and you’ll know how to build any interactive tool.

  Shown in order of appearance…
    1. status      – streaming progress bar
    2. message     – append text to the assistant bubble
    3. input       – text-input modal (awaits user)
    4. confirmation– yes/no modal (awaits user)
    5. citation    – collapsible Sources panel
    6. replace     – edits the assistant bubble in-place
"""

from __future__ import annotations
import asyncio, time
from typing import Awaitable, Callable, Dict

from pydantic import BaseModel, Field  # Only for the “Valves” settings panel


# ── Aliases that match the injections you get at runtime ───────────────
Emitter = Callable[[Dict[str, any]], Awaitable[None]]
Caller = Callable[[Dict[str, any]], Awaitable[any]]
# -----------------------------------------------------------------------


class Tools:
    # 🛠 1) Global knobs that appear under “Tool Settings” in WebUI
    class Valves(BaseModel):
        units: int = Field(4, description="Fake work-units to process")
        delay: float = Field(0.6, description="Seconds to wait between units")

    def __init__(self) -> None:
        self.valves = self.Valves()

    # 🛠 2) The single public method – becomes the tool name
    async def playground(
        self,
        units: int = None,
        __event_emitter__: Emitter | None = None,
        __event_call__: Caller | None = None,
    ) -> str:
        """Streams, prompts, confirms, cites, then edits its own bubble."""

        # Mini helper so we can just   await emit({...})
        async def emit(evt: Dict):
            if __event_emitter__:
                await __event_emitter__(evt)

        # ---------- STEP 0  •  decide how much “work” to do -------------
        total = units if isinstance(units, int) and units > 0 else self.valves.units

        # ---------- STEP 1  •  put a placeholder message in the chat ----
        await emit(
            {"type": "message", "data": {"content": "⏳ *Setting up the demo…*"}}
        )

        # ---------- STEP 2  •  start a progress bar ---------------------
        await emit(
            {
                "type": "status",
                "data": {"description": f"🚀 starting {total} units", "done": False},
            }
        )

        # ---------- STEP 3  •  simulate work & stream updates -----------
        for idx in range(1, total + 1):
            await asyncio.sleep(self.valves.delay)
            await emit(
                {
                    "type": "status",
                    "data": {"description": f"…unit {idx}/{total}", "done": False},
                }
            )

            # ── Mid-way: interactive break (only once)
            if idx == total // 2 and __event_call__:
                # 3A) Ask for a note (text-input modal)
                note = (
                    await __event_call__(
                        {
                            "type": "input",
                            "data": {
                                "title": "Add a note (optional)",
                                "message": "Enter any text to inject into the chat, "
                                "or leave blank.",
                                "placeholder": "my note",
                            },
                        }
                    )
                    or ""
                )

                # 3B) Confirm we should continue (yes/no modal)
                keep_going = await __event_call__(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": "Continue processing?",
                            "message": f"We’re half-way ({idx}/{total}). Continue?",
                        },
                    }
                )

                if not keep_going:
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

        # ---------- STEP 4  •  attach a citation block ------------------
        await emit(
            {
                "type": "citation",
                "data": {
                    "document": [f"Demo processed **{total}** units of fake work."],
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

        # ---------- STEP 5  •  mark the progress bar ‘done’ -------------
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

        # ---------- STEP 6  •  overwrite the first bubble ---------------
        final_text = f"🎉 Completed {total} units successfully."
        await emit({"type": "replace", "data": {"content": final_text}})

        # ---------- STEP 7  •  normal Python return ---------------------
        return final_text
