"""
title: Prompt Enrichment
id: prompt_enrichment_filter
description: Append user-specific context to the system prompt.
git_url: https://github.com/jrkropp/open-webui-developer-toolkit.git
required_open_webui_version: 0.6.10
version: 0.1.0
"""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        CACHE_TTL_SECONDS: int = Field(
            default=3600, description="Seconds before cached user data expires."
        )
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        self.icon = ""
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def _gather_user_info(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder for external user information retrieval (e.g., M365)."""
        # TODO: Implement retrieval logic for user information.
        return {}

    async def _get_user_info(self, user: Dict[str, Any]) -> Dict[str, Any]:
        user_id = user.get("id") or user.get("email")
        if not user_id:
            return {}

        now = time.time()
        cached = self._cache.get(user_id)
        if cached and cached["expires_at"] > now:
            return cached["data"]

        data = await self._gather_user_info(user)
        self._cache[user_id] = {
            "data": data,
            "expires_at": now + self.valves.CACHE_TTL_SECONDS,
        }
        return data

    async def inlet(
        self,
        body: Dict[str, Any],
        __user__: Dict[str, Any],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]] | None = None,
        __metadata__: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Append cached user information to the system prompt before the manifold."""
        user_info = await self._get_user_info(__user__ or {})
        if not user_info:
            return body

        enrichment_prompt = "\n".join(f"{k}: {v}" for k, v in user_info.items())

        messages = body.setdefault("messages", [])
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = f"{msg.get('content', '')}\n{enrichment_prompt}".strip()
                break
        else:
            messages.insert(0, {"role": "system", "content": enrichment_prompt})

        return body
