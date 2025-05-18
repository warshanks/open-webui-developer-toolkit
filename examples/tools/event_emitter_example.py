"""
title: Event Emitter Example
author: Open-WebUI Docs Team
version: 1.5
license: MIT
description: |
  Demonstrates how tools can drive the WebUI in real time.
  Functions receive two special parameters:

  • ``__event_emitter__`` – Sends non-blocking UI events over the
    ``chat-events`` websocket. ``Chat.svelte`` handles the following ``type``
    values:
      - ``status`` – update the progress bar.
      - ``message`` / ``chat:message:delta`` – append text to the current
        bubble.
      - ``chat:message`` / ``replace`` – replace the message contents.
      - ``files`` / ``chat:message:files`` – attach file metadata.
      - ``citation`` / ``source`` – add collapsible source blocks (use
        ``data.type == 'code_execution'`` for interpreter results).
      - ``chat:title`` – rename the chat.
      - ``chat:tags`` – refresh sidebar tags.
      - ``notification`` – toast (``info``/``success``/``warning``/``error``).
      - ``chat:completion`` – stream model tokens; also emits voice events
        (``chat:start`` → ``chat`` → ``chat:finish``).
      - ``execute`` – run JavaScript (non-blocking) without waiting
        for the result.

  • ``__event_call__`` – Opens a blocking modal. ``type`` values:
      ``confirmation`` or ``input`` (returns the user response)
      and ``execute`` (returns the JS result).

  This sample inserts a floating banner via ``execute`` and updates it
  as work progresses. The banner is removed once processing completes.
"""

from __future__ import annotations
import asyncio
import time
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
        # HTML is allowed inside markdown messages
        await emit({"type": "message", "data": {"content": "<b>HTML demo:</b> <em>Hello WebUI</em>"}})

        # Create a floating banner that will show live progress
        if __event_call__:
            await __event_call__(
                {
                    "type": "execute",
                    "data": {
                        "code": """
if (!document.getElementById('demo-banner')) {
  const div = document.createElement('div');
  div.id = 'demo-banner';
  div.style.cssText = 'position:fixed;top:10px;right:10px;padding:8px;background:#ffc;border:1px solid #444;z-index:1000;';
  div.textContent = 'Starting...';
  document.body.appendChild(div);
}
return 'banner ready';
"""
                    },
                }
            )
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
            if __event_call__:
                await __event_call__(
                    {
                        "type": "execute",
                        "data": {
                            "code": f"document.getElementById('demo-banner').textContent = 'Unit {idx}/{total}';"
                        },
                    }
                )
            # Stream delta text to the current bubble
            await emit({"type": "chat:message:delta", "data": {"content": f" {idx}"}})

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

                # Execute arbitrary JavaScript in the user's browser
                result = await __event_call__(
                    {
                        "type": "execute",
                        "data": {"code": "return 2 + 2"},
                    }
                )
                await emit(
                    {
                        "type": "message",
                        "data": {"content": f"🔢 JS returned: {result}"},
                    }
                )


                # Update banner via JavaScript
                await __event_call__(
                    {
                        "type": "execute",
                        "data": {
                            "code": f"document.getElementById('demo-banner').textContent = 'Halfway there ({idx}/{total})';"
                        },
                    }
                )

        # Emit tokens one by one using chat:completion
        stream_text = "Streaming via chat:completion"
        for char in stream_text:
            await asyncio.sleep(0.05)
            await emit(
                {
                    "type": "chat:completion",
                    "data": {"choices": [{"delta": {"content": char}}]},
                }
            )
        await emit(
            {
                "type": "chat:completion",
                "data": {"done": True, "choices": [{"message": {"content": stream_text}}]},
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

        # Example code execution block attached to the message
        await emit(
            {
                "type": "source",
                "data": {
                    "type": "code_execution",
                    "id": "calc",
                    "name": "2 + 2",
                    "code": "print(2 + 2)",
                    "language": "python",
                    "result": {"output": "4"},
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

        if __event_call__:
            await __event_call__(
                {
                    "type": "execute",
                    "data": {
                        "code": "document.getElementById('demo-banner')?.remove();"
                    },
                }
            )

        final_msg = f"🎉 Completed {total} units successfully."
        await emit({"type": "replace", "data": {"content": final_msg}})
        return final_msg
