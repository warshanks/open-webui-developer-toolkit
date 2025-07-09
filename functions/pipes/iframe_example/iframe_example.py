"""
title: IFrame Demo
id: iframe_example
author: OpenAI Codex
description: Demonstrates yielding an iframe snippet directly to the chat.
version: 1.0.0
license: MIT
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Awaitable, Callable


class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None,
        __metadata__: dict[str, Any] | None = None,
        *_,
    ) -> AsyncGenerator[str, None]:
        """Stream a simple iframe example to the user."""

        # Introductory text
        yield "Here is a sample iframe rendered in the chat:\n\n"

        # Inline HTML will be recognized by the frontend renderer
        yield (
            '<iframe src="https://example.com" ' 
            'width="100%" height="200" ' 
            'sandbox="allow-scripts allow-same-origin"></iframe>'
        )
