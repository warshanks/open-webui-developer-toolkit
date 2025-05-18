"""
title: Event Emitter Example
author: Open-WebUI Docs Team
author_url: https://github.com/open-webui
git_url: https://github.com/open-webui/open-webui-developer-toolkit
version: 4.4
license: MIT
required_open_webui_version: 0.4.0
description: |
  Demonstrates how to communicate from Python to the Open WebUI chat interface using two built-in functions:

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
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

# Runtime injection aliases for readability
Emitter = Callable[[dict[str, Any]], Awaitable[None]]
Caller = Callable[[dict[str, Any]], Awaitable[Any]]

# JavaScript snippets used to display a temporary banner in the UI
BANNER_ADD_JS = """
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

BANNER_REMOVE_JS = (
    "const b=document.getElementById('demo-banner');"
    "if(b){b.style.opacity='0';setTimeout(()=>b.remove(),300);}"
)


class Tools:
    """Collection of example tools."""

    # UI-visible “settings” pane ────────────────────────────────────
    class Valves(BaseModel):
        """Parameters exposed to the user interface."""

        units: int = Field(4, description="Fake work-units to process")
        delay: float = Field(0.6, description="Seconds between units")

    class UserValves(BaseModel):
        """Per-user configuration shown in the user settings pane."""

        show_banner: bool = Field(True, description="Display a banner while running")

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()
        # Disable automatic citations so custom ones are respected
        self.citation = False

    async def example_tool(
        self,
        units: int | None = None,
        __event_emitter__: Emitter | None = None,
        __event_call__: Caller | None = None,
        __user__: dict | None = None,
    ) -> str:
        """Demonstrate the built-in ``__event_*`` functions.

        Parameters
        ----------
        units:
            Override the number of work units to process.
        __user__:
            Dictionary with user information and optional ``UserValves``.
        """

        # ``__event_emitter__`` broadcasts events to the browser while
        # ``__event_call__`` waits for a response from the user interface.

        async def emit(evt: dict[str, Any]) -> None:
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

        async def run_js(code: str) -> Any:
            """Execute ``code`` in the browser and return the result."""
            if __event_call__:
                return await __event_call__({"type": "execute", "data": {"code": code}})
            return None

        total = units if isinstance(units, int) and units > 0 else self.valves.units
        if __user__:
            user_valves = __user__.get("valves", {})
            if isinstance(user_valves, dict):
                total = user_valves.get("units", total)
                show_banner = user_valves.get("show_banner", self.user_valves.show_banner)
            else:
                total = getattr(user_valves, "units", total)
                show_banner = getattr(user_valves, "show_banner", self.user_valves.show_banner)
        else:
            show_banner = self.user_valves.show_banner

        # Intro notification and chat line
        await emit(
            {
                "type": "notification",
                "data": {"type": "info", "content": "Starting demo"},
            }
        )
        user_name = (__user__ or {}).get("name")
        greeting = (
            f"🧪 Beginning event demo for {user_name}." if user_name else "🧪 Beginning event demo."
        )
        await emit({"type": "message", "data": {"content": greeting}})

        # ----- temporary banner -----
        if show_banner:
            await run_js(BANNER_ADD_JS)

        if not await confirm("Banner added. Continue to progress demo?"):
            if show_banner:
                await run_js(BANNER_REMOVE_JS)
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
                (
                    "const el=document.getElementById('demo-banner-text');"
                    f" if(el) el.textContent='Step {idx}/{total}';"
                )
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
            " if(el){el.textContent='Progress finished \u2713';}"
        )

        if not await confirm("Progress complete. Provide a note?"):
            if show_banner:
                await run_js(BANNER_REMOVE_JS)
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
            if show_banner:
                await run_js(BANNER_REMOVE_JS)
            return "Demo cancelled."

        js_result = await run_js("return 2 + 2")
        await emit(
            {"type": "message", "data": {"content": f"🔢 JS result: {js_result}"}}
        )

        if not await confirm("Show citation example?"):
            if show_banner:
                await run_js(BANNER_REMOVE_JS)
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
            if show_banner:
                await run_js(BANNER_REMOVE_JS)
            return "Demo cancelled."

        final_msg = "🎉 Event demo finished successfully."
        await emit({"type": "replace", "data": {"content": final_msg}})

        await emit(
            {
                "type": "notification",
                "data": {"type": "success", "content": "Demo finished"},
            }
        )
        if show_banner:
            await run_js(BANNER_REMOVE_JS)

        return final_msg
