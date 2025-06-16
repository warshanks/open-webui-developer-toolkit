"""
title: Invisible Message Encoding (v2 – minimal link)
id: invisible_message_encoding_pipe
description: |
    Stores a hidden string in an empty-text Markdown link: `[](mySecret)`.
    The link is invisible, and safe for Markdown layout (unlike using invisible width characters which break markdown).
author: Justin Kropp
version: 2.3.0
license: MIT
"""

import re
from typing import Any, AsyncGenerator, Awaitable, Callable

# ——— helpers ——————————————————————————————————

LINK_RE = re.compile(r"\[\]\(([^)\s]+)\)")

def encode_hidden_link(secret: str) -> str:
    """Return an invisible link line carrying *secret*."""
    return f"[]({secret})\n"          # one newline → no extra spacer

def decode_hidden_link(md: str) -> str | None:
    """Extract the first hidden-link payload in *md*."""
    m = LINK_RE.search(md)
    return m.group(1) if m else None

def find_secret(messages) -> str | None:
    for msg in reversed(messages):
        if secret := decode_hidden_link(msg.get("content", "")):
            return secret
    return None

# ——— Pipe ———————————————————————————————————

class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None,
        __event_call__: Callable[[dict[str, Any]], Awaitable[Any]] | None,
        *_,
    ) -> AsyncGenerator[str, None]:

        # 1 — decode if a previous secret exists
        if (secret := find_secret(body.get("messages", []))) is not None:
            yield f"🔓 **Decoded message:** `{secret}`"
            return

        # 2 — prompt user for a new secret
        user_input = await __event_call__(
            {
                "type": "input",
                "data": {
                    "title": "Enter a secret message",
                    "message": "Type something you'd like to hide invisibly.",
                    "placeholder": "Your hidden message…",
                },
            }
        )

        if not user_input:
            yield "⚠️ No message provided!"
            return

        # 3 — confirm and embed the invisible link
        hidden_link = encode_hidden_link(user_input)
        yield (
            "✨ Your message has been **encoded invisibly** in this response. "
            "Send another message to decode it.\n"
            f"{hidden_link}"
        )