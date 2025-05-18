"""
title: Event Emitter Example
author: Open-WebUI Docs Team
version: 2.0
license: MIT
description: |
  A concise tour of Open WebUI’s event system. Tools emit events to the
  front‑end via ``__event_emitter__`` and ``__event_call__``.
  Core ``type`` values include:
    - ``status`` – progress bar updates
    - ``message``/``chat:message:delta`` – append text to the bubble
    - ``chat:message``/``replace`` – replace message contents
    - ``citation``/``source`` – collapsible source blocks
    - ``notification`` – toast popups
    - ``confirmation``/``input`` – blocking modals for user feedback
    - ``execute`` – run arbitrary JavaScript in the browser

  This example walks through each event with confirmations between steps
  and cleans up a temporary banner when finished.
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
            if __event_emitter__:
                await __event_emitter__(evt)

        async def confirm(msg: str) -> bool:
            if __event_call__:
                return await __event_call__({"type": "confirmation", "data": {"title": "Event Demo", "message": msg}})
            return True

        async def run_js(code: str) -> any:
            if __event_call__:
                return await __event_call__({"type": "execute", "data": {"code": code}})
            return None

        total = units if isinstance(units, int) and units > 0 else self.valves.units

        await emit({"type": "notification", "data": {"type": "info", "content": "Starting demo"}})
        await emit({"type": "message", "data": {"content": "🧪 Beginning event demo."}})

        # --- banner ------------------------------------------------------
        await run_js(
            """
if (!document.getElementById('demo-banner')) {
  const div = document.createElement('div');
  div.id = 'demo-banner';
  div.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);padding:6px 12px;background:#bef264;border-radius:6px;font-weight:bold;z-index:9999';
  div.textContent = 'Event demo running...';
  document.body.appendChild(div);
}
"""
        )

        if not await confirm("Banner added. Continue with progress demo?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        # --- status updates ---------------------------------------------
        await emit({"type": "status", "data": {"description": "Progress", "done": False}})
        for idx in range(1, total + 1):
            await asyncio.sleep(self.valves.delay)
            await emit({"type": "status", "data": {"description": f"Step {idx}/{total}", "done": False}})
            await run_js(f"document.getElementById('demo-banner').textContent = 'Step {idx} of {total}';")
        await emit({"type": "status", "data": {"description": "Progress complete", "done": True, "style": "success"}})

        if not await confirm("Progress complete. Provide a note?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        note = ""
        if __event_call__:
            note = await __event_call__({
                "type": "input",
                "data": {
                    "title": "Optional note",
                    "message": "Enter text to display in the chat",
                    "placeholder": "my note",
                },
            }) or ""

        if note:
            await emit({"type": "message", "data": {"content": f"📝 Note: {note}"}})

        if not await confirm("Show HTML rendering example?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        # --- HTML message -----------------------------------------------
        await emit({"type": "chat:message", "data": {"content": "<b>Bold</b> <i>HTML</i> demo"}})

        js_result = await run_js("return 2 + 2")
        await emit({"type": "message", "data": {"content": f"🔢 JS result: {js_result}"}})

        if not await confirm("Show citation example?"):
            await run_js("document.getElementById('demo-banner')?.remove();")
            return "Demo cancelled."

        # --- citation ----------------------------------------------------
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
