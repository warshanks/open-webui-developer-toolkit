"""
title: Citations Example
id: citations_example
author: OpenAI Codex
description: Demonstrate how to emit citations from a pipe.
version: 1.0.0
license: MIT
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable


class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        *_,
    ) -> None:
        """Emit a short message with two example citations."""

        sources = [
            {
                "source": {"name": "Example Source 1"},
                "document": ["Example document snippet one."],
                "metadata": [{"source": "https://example.com/1"}],
            },
            {
                "source": {"name": "Example Source 2"},
                "document": ["Another snippet from a second source."],
                "metadata": [{"source": "https://example.com/2"}],
            },
        ]

        await __event_emitter__(
            {
                "type": "chat:completion",
                "data": {
                    "content": "This example cites two references [1][2].",
                    "done": True,
                    "sources": sources,
                },
            }
        )
        return None
