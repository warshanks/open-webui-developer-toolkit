"""
title: Debug
id: debug_toggle_filter
description: Attach session logs and input data as citations for debugging.
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.10
"""

from __future__ import annotations

import datetime
import json
import logging
from collections import defaultdict, deque
from contextvars import ContextVar
from typing import Any, Callable, Awaitable, Optional

from fastapi import Request
from pydantic import BaseModel

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "x-forwarded-for",
    "x-envoy-external-address",
}


class SessionLogger:
    """Session-aware logger that stores logs in memory."""

    session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
    log_level: ContextVar[int] = ContextVar("log_level", default=logging.INFO)
    logs: defaultdict[str | None, deque[str]] = defaultdict(lambda: deque(maxlen=1000))

    @classmethod
    def get_logger(cls, name: str = __name__) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.filters.clear()
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        def _filter(record: logging.LogRecord) -> bool:
            record.session_id = cls.session_id.get()
            return record.levelno >= cls.log_level.get()

        logger.addFilter(_filter)

        mem = logging.Handler()
        mem.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        mem.emit = (
            lambda r: cls.logs[r.session_id].append(mem.format(r)) if r.session_id else None
        )
        logger.addHandler(mem)
        return logger


class Filter:
    class Valves(BaseModel):
        priority: int = 0

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj4KICA8Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIvPgogIDxsaW5lIHgxPSIyIiB5MT0iMTIiIHgyPSIyMiIgeTI9IjEyIi8+CiAgPHBhdGggZD0iTTEyIDJhMTUgMTUgMCAwIDEgMCAyMCAxNSAxNSAwIDAgMSAwLTIweiIvPgo8L3N2Zz4="
        )
        self.logger = SessionLogger.get_logger(__name__)
        self._inputs: dict[str, Any] = {}

    async def inlet(
        self,
        body: dict[str, Any],
        __metadata__: Optional[dict[str, Any]] = None,
        __user__: Optional[dict[str, Any]] = None,
        __request__: Optional[Request] = None,
        __files__: Optional[list[dict[str, Any]]] = None,
        __tools__: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        SessionLogger.session_id.set((__metadata__ or {}).get("session_id"))
        SessionLogger.log_level.set(logging.DEBUG)
        self.logger.debug("Debug filter enabled")
        self._inputs = {
            "body": _safe_json(body),
            "__metadata__": _safe_json(__metadata__ or {}),
            "__user__": _safe_json(__user__ or {}),
            "__request__": _sanitize_request(__request__) if __request__ else {},
            "__files__": _safe_json(__files__ or []),
            "__tools__": _safe_json(__tools__ or {}),
        }
        return body

    async def outlet(
        self,
        body: dict[str, Any],
        __event_emitter__: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
    ) -> dict[str, Any]:
        if __event_emitter__:
            for name, value in self._inputs.items():
                await __event_emitter__(
                    {
                        "type": "citation",
                        "data": {
                            "document": [json.dumps(value, indent=2)],
                            "metadata": [
                                {
                                    "date_accessed": datetime.datetime.utcnow().isoformat(),
                                    "source": name,
                                }
                            ],
                            "source": {"name": name},
                        },
                    }
                )
            session_id = SessionLogger.session_id.get()
            logs = list(SessionLogger.logs.get(session_id, []))
            if logs:
                await __event_emitter__(
                    {
                        "type": "citation",
                        "data": {
                            "document": ["\n".join(logs)],
                            "metadata": [
                                {
                                    "date_accessed": datetime.datetime.utcnow().isoformat(),
                                    "source": "Debug Logs",
                                }
                            ],
                            "source": {"name": "Debug Logs"},
                        },
                    }
                )
            SessionLogger.logs.pop(session_id, None)
        SessionLogger.log_level.set(logging.INFO)
        return body


def _sanitize_request(request: Request) -> dict[str, Any]:
    headers = {
        k: ("[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v)
        for k, v in request.headers.items()
    }
    return {"method": request.method, "url": str(request.url), "headers": headers}


def _safe_json(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_json(v) for v in obj]
    if hasattr(obj, "dict"):
        try:
            return _safe_json(obj.dict())
        except Exception:
            pass
    if hasattr(obj, "model_dump"):
        try:
            return _safe_json(obj.model_dump())
        except Exception:
            pass
    return f"<UNSERIALIZABLE {type(obj).__name__}>"
