"""
title: Invisible Message Encoding
id: invisible_message_encoding_pipe
description:
    Persist a secret by embedding it in a markdown comment so it remains hidden
    from the UI. Simply place the text between square brackets followed by
    ``: #`` – for example ``[my secret]: #``. Earlier versions used a more
    complex ``[hidden_secret:v1:<b64>]`` format, but this example keeps the
    concept simple and easy to understand.
author: Justin Kropp
version: 2.5.1
license: MIT
"""

import re
from typing import Any, AsyncGenerator, Awaitable, Callable

# ——— helpers ——————————————————————————————————

COMMENT_RE = re.compile(r"\[([^\n\]]+)\]: #")

def encode_hidden_comment(secret: str) -> str:
    """Return a newline wrapped comment carrying *secret*."""
    return f"\n[{secret}]: #\n"

def decode_hidden_comment(md: str) -> str | None:
    """Extract the first hidden-comment payload in *md*."""
    if m := COMMENT_RE.search(md):
        return m.group(1)
    return None

def find_secret(messages) -> str | None:
    for msg in reversed(messages):
        if secret := decode_hidden_comment(msg.get("content", "")):
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

        # 3 — confirm and embed the invisible comment
        hidden_comment = encode_hidden_comment(user_input)
        yield (
            "✨ Your message has been **encoded invisibly** in this response. "
            "Send another message to decode it.\n"
            f"{hidden_comment}"
        )
