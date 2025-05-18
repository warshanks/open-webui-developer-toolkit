"""
title: Universal Example Tool
version: 1.1.0
author: OpenWebUI Toolkit
author_url: https://example.com
license: MIT
description: |
    Complete reference for building Open WebUI tools without external dependencies.
    Demonstrates valves, environment variables, __event_emitter__ and __event_call__,
    confirmation dialogs, input prompts, client-side code execution and custom citations.
requirements: sympy
"""

from datetime import datetime
from typing import Optional, Callable, Awaitable, Any, Dict
import os

import sympy as sp
from pydantic import BaseModel, Field


class Tools:
    """Comprehensive reference implementation for tool authors."""

    class Valves(BaseModel):
        """User-configurable values accessible from the WebUI."""

        default_greeting: str = Field(
            default="Hello",
            description="Greeting used by greet_user when no name is supplied.",
        )
        citation_demo_enabled: bool = Field(
            default=True,
            description="If True, demo_citation emits a sample citation.",
        )
        notes_limit: int = Field(
            default_factory=lambda: int(os.getenv("UNIVERSAL_NOTES_LIMIT", "5")),
            description="Maximum number of notes stored by manage_notes.",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.citation = False  # disable built-in citations
        self.notes: list[str] = []

    # ------------------------------------------------------------------
    # 1. Basic synchronous helpers
    # ------------------------------------------------------------------
    def greet_user(self, name: str = "") -> str:
        """Return a friendly greeting."""
        greeting = self.valves.default_greeting
        target = name or "there"
        return f"{greeting}, {target}!"

    def calculate_expression(self, expression: str) -> str:
        """Evaluate a mathematical expression like '2+3' or 'sqrt(16)'."""
        if "=" in expression:
            return "Equations (with '=') are not allowed."
        try:
            val = sp.sympify(expression).evalf()
            text = str(val).rstrip("0").rstrip(".") if "." in str(val) else str(val)
            return f"{expression} = {text}"
        except Exception:
            return "Invalid expression"

    def get_user_info(self, __user__: Dict[str, Any] = {}) -> str:
        """Return fields from the special ``__user__`` argument."""
        if not __user__:
            return "No user information provided."
        parts = []
        if "name" in __user__:
            parts.append(f"Name: {__user__['name']}")
        if "email" in __user__:
            parts.append(f"Email: {__user__['email']}")
        if "id" in __user__:
            parts.append(f"ID: {__user__['id']}")
        return " | ".join(parts) if parts else "User fields not found."

    # ------------------------------------------------------------------
    # 2. Async method demonstrating __event_emitter__ and __event_call__
    # ------------------------------------------------------------------
    async def manage_notes(
        self,
        action: str = "add",
        index: int = 0,
        text: str = "",
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
        __event_call__: Optional[Callable[[dict], Awaitable[Any]]] = None,
    ) -> str:
        """Add, edit or remove notes with interactive prompts."""
        await _safe_emit_status(__event_emitter__, "Processing note action...", done=False)

        if len(self.notes) > self.valves.notes_limit:
            self.notes = self.notes[-self.valves.notes_limit :]

        if action == "add":
            if not text and __event_call__:
                text = await __event_call__(
                    {
                        "type": "input",
                        "data": {
                            "title": "New Note",
                            "message": "Enter note text",
                            "placeholder": "My note",
                        },
                    }
                ) or ""
            if not text:
                await _safe_emit_status(__event_emitter__, "No note text provided.", done=True)
                return "No note added."
            self.notes.append(text)
            await _safe_emit_notification(
                __event_emitter__, {"type": "success", "content": "Note added"}
            )
        elif action == "remove":
            if index < 0 or index >= len(self.notes):
                await _safe_emit_status(__event_emitter__, "Index out of range.", done=True)
                return "Invalid note index."
            if __event_call__:
                confirm = await __event_call__(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": "Delete Note",
                            "message": f"Delete note #{index + 1}?",
                        },
                    }
                )
                if not confirm:
                    await _safe_emit_status(__event_emitter__, "Deletion cancelled.", done=True)
                    return "Cancelled."
            note = self.notes.pop(index)
            await _safe_emit_notification(
                __event_emitter__, {"type": "warning", "content": f"Deleted note: {note}"}
            )
        elif action == "edit":
            if index < 0 or index >= len(self.notes):
                await _safe_emit_status(__event_emitter__, "Index out of range.", done=True)
                return "Invalid note index."
            if __event_call__:
                text = await __event_call__(
                    {
                        "type": "input",
                        "data": {
                            "title": "Edit Note",
                            "message": "Update note text",
                            "placeholder": "Note",
                            "value": self.notes[index],
                        },
                    }
                ) or ""
            if not text:
                await _safe_emit_status(__event_emitter__, "Edit cancelled.", done=True)
                return "Cancelled."
            self.notes[index] = text
            await _safe_emit_notification(
                __event_emitter__, {"type": "success", "content": "Note updated"}
            )
        elif action == "alert":
            if __event_call__:
                await __event_call__(
                    {
                        "type": "execute",
                        "data": {"code": f'alert("Notes count: {len(self.notes)}");'},
                    }
                )
            await _safe_emit_notification(
                __event_emitter__, {"type": "info", "content": "Alert executed"}
            )
        else:
            await _safe_emit_status(__event_emitter__, f"Unknown action: {action}", done=True)
            return "Invalid action."

        await _safe_emit_status(__event_emitter__, "Done", done=True)
        return " | ".join(f"{i+1}. {n}" for i, n in enumerate(self.notes))

    # ------------------------------------------------------------------
    # 3. Custom citation event
    # ------------------------------------------------------------------
    async def demo_citation(
        self,
        note: str = "A quick example of custom citation usage.",
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        if not self.valves.citation_demo_enabled:
            return "Citation demo is disabled by tool settings."
        if not __event_emitter__:
            return "No event emitter to display citation."
        citation_event = {
            "type": "citation",
            "data": {
                "document": [note],
                "metadata": [
                    {"date_accessed": datetime.now().isoformat(), "source": "Demo Source"}
                ],
                "source": {"name": "Demo Source", "url": "https://example.com/demoCitation"},
            },
        }
        await __event_emitter__(citation_event)
        return "Emitted custom citation event."


async def _safe_emit_status(
    emitter: Optional[Callable[[dict], Awaitable[None]]],
    description: str,
    done: bool,
) -> None:
    """Helper to emit status updates without raising on failure."""
    if not emitter:
        return
    try:
        await emitter({"type": "status", "data": {"description": description, "done": done}})
    except Exception:
        pass


async def _safe_emit_notification(
    emitter: Optional[Callable[[dict], Awaitable[None]]],
    data: dict,
) -> None:
    """Safely send a notification event via ``__event_emitter__``."""
    if not emitter:
        return
    try:
        await emitter({"type": "notification", "data": data})
    except Exception:
        pass

