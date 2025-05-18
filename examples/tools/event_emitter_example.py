"""
title: Event Emitter Example
author: Open-WebUI Docs Team
version: 3.0
license: MIT
description: |
  Guided tour of the front‑end event system. Tools emit dictionaries via
  ``__event_emitter__`` while ``__event_call__`` waits for user input.

  Supported event ``type`` values include:

    - ``status``       – progress indicator shown above a message
    - ``message``      – append Markdown/HTML to the current response
    - ``chat:message`` – replace the message body entirely
    - ``replace``      – synonym for ``chat:message``
    - ``citation``     – collapsible citation blocks
    - ``notification`` – toast popup
    - ``confirmation`` – yes/no dialog
    - ``input``        – text entry dialog
    - ``execute``      – run a JavaScript snippet in the browser

  The ``playground`` method emits each of these events in sequence and
  uses confirmation dialogs so you can observe the UI updates step by
  step.
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

    # Public tool method demonstrating common event types
    async def playground(
        self,
        units: int | None = None,
        __event_emitter__: Emitter | None = None,
        __event_call__: Caller | None = None,
    ) -> str:

        async def emit(evt: Dict) -> None:
            """Send an event to the front‑end if possible."""
            if __event_emitter__:
                await __event_emitter__(evt)

        async def confirm(message: str) -> bool:
            """Block until the user clicks OK/Cancel."""
            if __event_call__:
                return await __event_call__(
                    {"type": "confirmation", "data": {"title": "Event Demo", "message": message}}
                )
            return True

        async def run_js(code: str) -> any:
            """Execute ``code`` in the browser and return the result."""
            if __event_call__:
                return await __event_call__({"type": "execute", "data": {"code": code}})
            return None

        total = units if isinstance(units, int) and units > 0 else self.valves.units

        # Intro notification and chat line
        await emit({"type": "notification", "data": {"type": "info", "content": "Starting demo"}})
        await emit({"type": "message", "data": {"content": "🧪 Beginning event demo."}})

        # ----- temporary banner -----
        await run_js(
            """
if (!document.getElementById('demo-banner')) {
  const div = document.createElement('div');
  div.id = 'demo-banner';
  div.innerHTML = '<span id="demo-banner-text">Event demo running...</span>';
  div.style.cssText = 'position:fixed;top:1rem;left:50%;transform:translateX(-50%);padding:8px 16px;background:linear-gradient(90deg,#6366f1,#8b5cf6);color:white;border-radius:8px;font-weight:600;z-index:9999';
  document.body.appendChild(div);
}
"""
        )

        if not await confirm("Banner added. Continue to progress demo?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        # ----- status events -----
        await emit({"type": "status", "data": {"description": "Progress", "done": False}})
        for idx in range(1, total + 1):
            await asyncio.sleep(self.valves.delay)
            await emit({"type": "status", "data": {"description": f"Step {idx}/{total}", "done": False}})
            await run_js(
                f"const el=document.getElementById('demo-banner-text'); if(el) el.textContent='Step {idx}/{total}';"
            )
        await emit(
            {"type": "status", "data": {"description": "Progress complete", "done": True, "style": "success"}}
        )

        if not await confirm("Progress complete. Provide a note?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        note = ""
        if __event_call__:
            note = await __event_call__(
                {
                    "type": "input",
                    "data": {
                        "title": "Optional note",
                        "message": "Enter text to display in the chat",
                        "placeholder": "my note",
                    },
                }
            ) or ""

        if note:
            await emit({"type": "message", "data": {"content": f"📝 {note}"}})

        if not await confirm("Show markup/HTML example?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        # ----- HTML / Markdown -----
        html_demo = "<details><summary>Click to expand</summary><b>HTML inside details</b></details>"
        await emit({"type": "chat:message", "data": {"content": html_demo}})

        js_result = await run_js("return 2 + 2")
        await emit({"type": "message", "data": {"content": f"🔢 JS result: {js_result}"}})

        if not await confirm("Show citation example?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        # ----- citation -----
        await emit(
            {
                "type": "citation",
                "data": {
                    "document": ["This text came from a *citation*."],
                    "metadata": [{"date_accessed": time.strftime("%Y-%m-%dT%H:%M:%SZ")}],
                    "source": {"name": "Event Demo", "url": "https://github.com/open-webui/open-webui"},
                },
            }
        )

        if not await confirm("Replace the final message and finish demo?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        final_msg = "🎉 Event demo finished successfully."
        await emit({"type": "replace", "data": {"content": final_msg}})

        await emit({"type": "notification", "data": {"type": "success", "content": "Demo finished"}})
        await run_js("document.getElementById('demo-banner')?.remove();")

        return final_msg
