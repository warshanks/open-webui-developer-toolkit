"""
title: Event Emitter Example
author: Open-WebUI Docs Team
version: 1.2
license: MIT
description: |
  This tool demonstrates how to use Open WebUI's event system.  Tool
  functions receive two injected parameters at runtime:

  • ``__event_emitter__`` – Sends non‑blocking updates over the
    ``chat-events`` websocket.  ``Chat.svelte`` maps the ``type`` field of each
    event to UI actions:
      - ``status`` – progress indicator updates.
      - ``message`` or ``chat:message:delta`` – append text to the current
        message bubble.
      - ``chat:message`` or ``replace`` – replace the bubble content.
      - ``files`` or ``chat:message:files`` – attach file metadata.
      - ``citation`` or ``source`` – add collapsible source blocks.
      - ``chat:title`` – rename the chat.
      - ``chat:tags`` – refresh sidebar tags.
      - ``notification`` – show a toast (``info``, ``success``, ``warning`` or
        ``error``).

  • ``__event_call__`` – Opens a modal and waits for user input.  Supported
    ``type`` values are ``confirmation`` and ``input`` (both return the
    user's response) and ``execute`` to run client-side JavaScript.

  ``Chat.svelte`` also exposes an ``EventTarget`` for voice features. It
  dispatches ``chat:start``, ``chat`` and ``chat:finish`` events while streaming
  so other components can play text-to-speech audio in real time.
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
        await emit(
            {
                "type": "notification",
                "data": {"type": "info", "content": "Starting demo"},
            }
        )
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

        await emit(
            {
                "type": "notification",
                "data": {"type": "success", "content": "Demo finished"},
            }
        )

        final_msg = f"🎉 Completed {total} units successfully."
        await emit({"type": "replace", "data": {"content": final_msg}})
        return final_msg
