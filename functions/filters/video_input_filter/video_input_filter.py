"""
title: Video Input
id: video_input
description: Sends attached videos to video-capable models (e.g. Kimi via OpenRouter) as video_url parts.
git_url: https://github.com/warshanks/open-webui-developer-toolkit.git
required_open_webui_version: 0.12.0
version: 0.1.0
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

from open_webui.models.files import Files
from open_webui.storage.provider import Storage
from pydantic import BaseModel, Field

# Open WebUI only turns image attachments into content parts.  Videos are
# stored untouched and reach the model as an <attached_files> tag (when native
# tools are on) plus an empty RAG source, so the model knows a file exists but
# never sees it.  This filter swaps those references for real video_url parts.
FILE_TAG_RE = re.compile(r"<file\b[^>]*/>")
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def _video_ids_in(content: Any) -> list[str]:
    ids = []
    for tag in FILE_TAG_RE.findall(_text_of(content)):
        attrs = dict(ATTR_RE.findall(tag))
        if attrs.get("content_type", "").startswith("video/") and attrs.get("id"):
            ids.append(attrs["id"])
    return ids


class Filter:
    class Valves(BaseModel):
        MAX_VIDEO_MB: int = Field(
            default=20,
            description="Videos larger than this are not sent; the model is told why instead.",
        )
        priority: int = Field(default=0, description="Priority level for the filter operations.")

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __user__: dict | None = None,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict:
        messages = body.get("messages") or []
        user_id = (__user__ or {}).get("id")
        user_messages = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if not user_messages or not user_id:
            return body

        wanted = {id(m): _video_ids_in(m.get("content")) for m in user_messages}

        # Without native tools there are no <attached_files> tags; fall back to
        # the current turn's uploads, which only belong to the last message.
        current_videos = [
            f.get("id") for f in body.get("files") or []
            if (f.get("content_type") or "").startswith("video/") and f.get("id")
        ]
        last = user_messages[-1]
        if not wanted[id(last)] and current_videos:
            wanted[id(last)] = current_videos

        cache: dict[str, dict] = {}
        for message in user_messages:
            parts = []
            for file_id in dict.fromkeys(wanted[id(message)]):
                if file_id not in cache:
                    cache[file_id] = await self._load_part(file_id, user_id, __event_emitter__)
                if cache[file_id]:
                    parts.append(cache[file_id])
            if not parts:
                continue
            content = message.get("content")
            if not isinstance(content, list):
                content = [{"type": "text", "text": content or ""}]
            message["content"] = [*content, *parts]

        # The empty RAG lookup on a video only produces a "no sources" step.
        if current_videos:
            body["files"] = [
                f for f in body.get("files") or []
                if not (f.get("content_type") or "").startswith("video/")
            ]
        return body

    async def _load_part(self, file_id: str, user_id: str, emitter) -> dict | None:
        file = await _maybe_await(Files.get_file_by_id(file_id))
        # File ids come from message text, so only ever send the requester's own uploads.
        if not file or file.user_id != user_id:
            return None

        meta = file.meta or {}
        name = meta.get("name") or file.filename
        content_type = meta.get("content_type") or "video/mp4"
        if not content_type.startswith("video/"):
            return None

        try:
            path = await asyncio.to_thread(Storage.get_file, file.path)
            size = os.path.getsize(path)
            if size > self.valves.MAX_VIDEO_MB * 1024 * 1024:
                note = f"Video '{name}' was not sent: {size / 1024 / 1024:.0f} MB is over the {self.valves.MAX_VIDEO_MB} MB limit."
                await self._notify(emitter, note)
                return {"type": "text", "text": f"[{note}]"}
            data = await asyncio.to_thread(_read_bytes, path)
        except (OSError, RuntimeError) as e:  # missing file, or a remote storage download failed
            await self._notify(emitter, f"Could not read video '{name}': {e}")
            return None

        url = f"data:{content_type};base64,{base64.b64encode(data).decode()}"
        return {"type": "video_url", "video_url": {"url": url}}

    async def _notify(self, emitter, content: str) -> None:
        if emitter:
            await emitter({"type": "notification", "data": {"type": "warning", "content": content}})
