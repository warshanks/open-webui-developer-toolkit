"""
title: Event Emitter Example
author: Open-WebUI Docs Team
version: 4.3
license: MIT
description: |
  This tool teaches how to communicate from Python to the Open WebUI chat interface using two built-in functions:

    1. __event_emitter__: sends updates directly to the chat UI (doesn't pause execution).
        - "status": display progress messages (e.g., "loading...").
        - "message": add plain text to the existing chat bubble.
        - "replace": completely replace the current chat message.
        - "citation": attach collapsible "source" information to messages.
        - "notification": show brief popup notifications on screen.

    2. __event_call__: shows pop-up dialogs that wait for user input (pauses execution until the user responds).
        - "confirmation": simple Yes/No dialog.
        - "input": prompt the user to type something.
        - "execute": run JavaScript in the user's browser and receive the result back into Python.

    Enable the tool and ask the LLM to run the 'example_tool' to test.
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

    async def example_tool(
        self,
        units: int = None,
        __event_emitter__: Emitter | None = None,
        __event_call__: Caller | None = None,
    ) -> str:

        # ``__event_emitter__`` broadcasts events to the browser while
        # ``__event_call__`` waits for a response from the user interface.

        async def emit(evt: Dict) -> None:
            """Send ``evt`` to the UI if possible."""
            if __event_emitter__:
                await __event_emitter__(evt)

        async def confirm(message: str) -> bool:
            """Show a yes/no dialog and return ``True`` if confirmed."""
            if __event_call__:
                return await __event_call__(
                    {
                        "type": "confirmation",
                        "data": {"title": "Event Demo", "message": message},
                    }
                )
            return True

        async def run_js(code: str) -> any:
            """Execute ``code`` in the browser and return the result."""
            if __event_call__:
                return await __event_call__({"type": "execute", "data": {"code": code}})
            return None

        total = units if isinstance(units, int) and units > 0 else self.valves.units

        # Intro notification and chat line
        await emit(
            {
                "type": "notification",
                "data": {"type": "info", "content": "Starting demo"},
            }
        )
        await emit({"type": "message", "data": {"content": "🧪 Beginning event demo."}})

        # ----- temporary banner -----
        banner_add_js = """
if (!document.getElementById('demo-banner')) {
  const div = document.createElement('div');
  div.id = 'demo-banner';
  div.innerHTML = '<span id="demo-banner-text">Event demo running...</span>';
  div.style.cssText = [
    'position:fixed',
    'top:1rem',
    'left:50%',
    'transform:translateX(-50%)',
    'padding:8px 16px',
    'background:linear-gradient(90deg,#6366f1,#9333ea)',
    'color:white',
    'border-radius:8px',
    'font-weight:600',
    'box-shadow:0 2px 8px rgba(0,0,0,.2)',
    'z-index:9999',
    'opacity:0',
    'transition:opacity 0.3s'
  ].join(';');
  document.body.appendChild(div);
  requestAnimationFrame(() => { div.style.opacity = '1'; });
}
"""
        banner_remove_js = (
            "const b=document.getElementById('demo-banner');"
            "if(b){b.style.opacity='0';setTimeout(()=>b.remove(),300);}"
        )

        await run_js(banner_add_js)

        if not await confirm("Banner added. Continue to progress demo?"):
            await run_js(banner_remove_js)
            return "Demo cancelled."

        # ----- status events -----
        await emit(
            {"type": "status", "data": {"description": "Progress", "done": False}}
        )
        for idx in range(1, total + 1):
            await asyncio.sleep(self.valves.delay)
            await emit(
                {
                    "type": "status",
                    "data": {"description": f"Step {idx}/{total}", "done": False},
                }
            )
            await run_js(
                f"const el=document.getElementById('demo-banner-text'); if(el) el.textContent='Step {idx}/{total}';"
            )
        await emit(
            {
                "type": "status",
                "data": {
                    "description": "Progress complete",
                    "done": True,
                    "style": "success",
                },
            }
        )
        await run_js(
            "const el=document.getElementById('demo-banner-text');"
            "if(el){el.textContent='Progress finished \u2713';}"
        )

        if not await confirm("Progress complete. Provide a note?"):
            await run_js(banner_remove_js)
            return "Demo cancelled."

        note = ""
        if __event_call__:
            note = (
                await __event_call__(
                    {
                        "type": "input",
                        "data": {
                            "title": "Optional note",
                            "message": "Enter text to display in the chat",
                            "placeholder": "my note",
                        },
                    }
                )
                or ""
            )

        if note:
            await emit({"type": "message", "data": {"content": f"📝 {note}"}})

        if not await confirm("Show markup/HTML example?"):
            await run_js(banner_remove_js)
            return "Demo cancelled."

        js_result = await run_js("return 2 + 2")
        await emit(
            {"type": "message", "data": {"content": f"🔢 JS result: {js_result}"}}
        )

        if not await confirm("Show citation example?"):
            await run_js(banner_remove_js)
            return "Demo cancelled."

        # ----- citation -----
        await emit(
            {
                "type": "citation",
                "data": {
                    "document": ["This text came from a *citation*."],
                    "metadata": [
                        {"date_accessed": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
                    ],
                    "source": {
                        "name": "Event Demo",
                        "url": "https://github.com/open-webui/open-webui",
                    },
                },
            }
        )

        if not await confirm("Replace the final message and finish demo?"):
            await run_js(banner_remove_js)
            return "Demo cancelled."

        final_msg = "🎉 Event demo finished successfully."
        await emit({"type": "replace", "data": {"content": final_msg}})

        await emit(
            {
                "type": "notification",
                "data": {"type": "success", "content": "Demo finished"},
            }
        )
        await run_js(banner_remove_js)

        return final_msg
