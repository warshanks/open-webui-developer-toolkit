"""
title: OpenAI Responses Companion Filter
id: openai_responses_companion_filter
description: Handles file uploads for the OpenAI Responses manifold.
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.3
version: 0.1.0
"""

from __future__ import annotations
from ast import Dict, List
from collections import defaultdict, deque
from contextvars import ContextVar
import datetime
import logging
import os
import sys

import aiohttp
from pydantic import BaseModel, Field
from typing import Any, Awaitable, Callable, Literal, Optional


class Filter:
    class Valves(BaseModel):
        LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
            default=os.getenv("GLOBAL_LOG_LEVEL", "INFO").upper(),
            description="Select logging level.  Recommend INFO or WARNING for production use. DEBUG is useful for development and debugging.",
        )
        pass

    class UserValves(BaseModel):
        """Per-user valve overrides."""
        LOG_LEVEL: Literal[
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "INHERIT"
        ] = Field(
            default="INHERIT",
            description="Select logging level. 'INHERIT' uses the pipe default.",
        )

    def __init__(self) -> None:
        self.file_handler = True  # disable built-in file injection
        self.citation = False  # disable built-in citation emittion

        self.valves = self.Valves()
        self.session: aiohttp.ClientSession | None = None
        self.logger = SessionLogger.get_logger(__name__)

    async def inlet(
        self,
        body: dict,
        __user__: dict[str, Any],
        __event_emitter__: Optional[callable] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """
        Process files before they reach the manifold.
        """
        valves = self._merge_valves(self.valves, self.UserValves.model_validate(__user__.get("valves", {})))

        # Set up session logger with session_id and log level
        SessionLogger.session_id.set(__metadata__.get("session_id", None))
        SessionLogger.log_level.set(getattr(logging, valves.LOG_LEVEL.upper(), logging.INFO))

        files: List[Dict] = (__metadata__ or {}).get("files")
        if not files:
            return body

        # Process each file
        for file in files:
            # Perform any necessary processing on the file
            """
            File Example: {'type': 'file', 'file': {'id': 'c5117234-2f9d-4c45-a780-9fa4fb40401e', 'user_id': 'a28e8ee4-1f0c-48da-a21f-a6b869fef275', 'hash': 'bdf63acefb200e00ff6852ae1228a6ca799cf362797b3c917f80c83abd55750e', 'filename': 'full_turn2.json', 'data': {'content': '[INSERTED FROM FULL PAYLOAD IN USER LOGS]'}, 'meta': {'name': 'full_turn2.json', 'content_type': 'application/json', 'size': 41, 'data': {}}, 'created_at': 1750274301, 'updated_at': 1750274301}, 'id': 'c5117234-2f9d-4c45-a780-9fa4fb40401e', 'url': '/api/v1/files/c5117234-2f9d-4c45-a780-9fa4fb40401e', 'name': 'full_turn2.json', 'status': 'uploaded', 'size': 41, 'error': '', 'itemId': '728a1c11-c935-45a1-b3c6-d016f5f46a44'}
            """
            self.logger.debug("Processing file: %s", file.get("name", "Unknown File"))
            self.logger.debug("File details: %s", file)

            pass

        # Emit logs if valves.LOG_LEVEL is set to DEBUG
        if valves.LOG_LEVEL == "DEBUG":
            session_id = SessionLogger.session_id.get()
            logs = SessionLogger.logs.get(session_id, [])
            if logs:
                await self._emit_citation(
                    __event_emitter__,
                    document="\n".join(logs),
                    source_name="Filter Debug Logs",
                )
            else:
                self.logger.warning("No debug logs found for session_id %s", session_id)

        return body

    async def outlet(self, body: dict) -> dict:
        """Placeholder for response post-processing."""
        return body
    
        # 4.7 Emitters (Front-end communication)
    async def _emit_error(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]],
        error_obj: Exception | str,
        *,
        show_error_message: bool = True,
        show_error_log_citation: bool = False,
        done: bool = False,
    ) -> None:
        """Log an error and optionally surface it to the UI.

        When ``show_error_log_citation`` is true the function also emits the
        collected debug logs as a citation block so users can inspect what went
        wrong.
        """
        error_message = str(error_obj)  # If it's an exception, convert to string
        self.logger.error("Error: %s", error_message)

        if show_error_message and event_emitter:
            await event_emitter(
                {
                    "type": "chat:completion",
                    "data": {
                        "error": {"message": error_message},
                        "done": done,
                    },
                }
            )

            # 2) Optionally emit the citation with logs
            if show_error_log_citation:
                session_id = SessionLogger.session_id.get()
                logs = SessionLogger.logs.get(session_id, [])
                if logs:
                    await self._emit_citation(
                        event_emitter,
                        "\n".join(logs),
                        "Error Logs",
                    )
                else:
                    self.logger.warning(
                        "No debug logs found for session_id %s", session_id
                    )

    async def _emit_citation(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        document: str | list[str],
        source_name: str,
    ) -> None:
        """Send a citation block to the UI if an emitter is available.

        ``document`` may be either a single string or a list of strings.  The
        function normalizes this input and emits a ``citation`` event containing
        the text and its source metadata.
        """
        if event_emitter is None:
            return

        if isinstance(document, list):
            doc_text = "\n".join(document)
        else:
            doc_text = document

        await event_emitter(
            {
                "type": "citation",
                "data": {
                    "document": [doc_text],
                    "metadata": [
                        {
                            "date_accessed": datetime.datetime.now().isoformat(),
                            "source": source_name,
                        }
                    ],
                    "source": {"name": source_name},
                },
            }
        )

    async def _emit_completion(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        *,
        content: str | None = "",                       # always included (may be "").  UI will stall if you leave it out.
        title:   str | None = None,                     # optional title.
        usage:   dict[str, Any] | None = None,          # optional usage block
        done:    bool = True,                           # True → final frame
    ) -> None:
        """Emit a ``chat:completion`` event if an emitter is present.

        The ``done`` flag indicates whether this is the final frame for the
        request.  When ``usage`` information is provided it is forwarded as part
        of the event data.
        """
        if event_emitter is None:
            return

        # Note: Open WebUI emits a final "chat:completion" event after the stream ends, which overwrites any previously emitted completion events' content and title in the UI.
        await event_emitter(
            {
                "type": "chat:completion",
                "data": {
                    "done": done,
                    "content": content,
                    **({"title": title} if title is not None else {}),
                    **({"usage": usage} if usage is not None else {}),
                }
            }
        )

    async def _emit_status(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        description: str,
        *,
        done: bool = False,
        hidden: bool = False,
    ) -> None:
        """Emit a short status update to the UI.

        ``hidden`` allows emitting a transient update that is not shown in the
        conversation transcript.
        """
        if event_emitter is None:
            return
        
        await event_emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": hidden},
            }
        )

    async def _emit_notification(
        self,
        event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
        content: str,
        *,
        level: Literal["info", "success", "warning", "error"] = "info",
    ) -> None:
        """Emit a toast-style notification to the UI.

        The ``level`` argument controls the styling of the notification banner.
        """
        if event_emitter is None:
            return

        await event_emitter(
            {"type": "notification", "data": {"type": level, "content": content}}
        )
    
    # 4.8 Internal Static Helpers
    def _merge_valves(self, global_valves, user_valves) -> "Filter.Valves":
        """Merge user-level valves into the global defaults.

        Any field set to ``"INHERIT"`` (case-insensitive) is ignored so the
        corresponding global value is preserved.
        """
        if not user_valves:
            return global_valves

        # Merge: update only fields not set to "INHERIT"
        update = {
            k: v
            for k, v in user_valves.model_dump().items()
            if v is not None and str(v).lower() != "inherit"
        }
        return global_valves.model_copy(update=update)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Utility Classes (Shared utilities)
# ─────────────────────────────────────────────────────────────────────────────
# Support classes used across the pipe implementation
class SessionLogger:
    session_id = ContextVar("session_id", default=None)
    log_level = ContextVar("log_level", default=logging.INFO)
    logs = defaultdict(lambda: deque(maxlen=1000))

    @classmethod
    def get_logger(cls, name=__name__):
        """Return a logger wired to the current ``SessionLogger`` context."""
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.filters.clear()
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Single combined filter
        def filter(record):
            record.session_id = cls.session_id.get()
            return record.levelno >= cls.log_level.get()

        logger.addFilter(filter)

        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("[%(levelname)s] [%(session_id)s] %(message)s"))
        logger.addHandler(console)

        # Memory handler
        mem = logging.Handler()
        mem.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        mem.emit = lambda r: cls.logs[r.session_id].append(mem.format(r)) if r.session_id else None
        logger.addHandler(mem)

        return logger

# In-memory store for debug logs keyed by message ID
logs_by_msg_id: dict[str, list[str]] = defaultdict(list)
# Context variable tracking the current message being processed
current_session_id: ContextVar[str | None] = ContextVar("current_session_id", default=None)