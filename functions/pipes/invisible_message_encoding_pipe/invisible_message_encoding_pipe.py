"""
title: Invisible Message Encoding
id: invisible_message_encoding_pipe
description:
    Encode user input invisibly in assistant responses and decode it from later messages.

notes:
    - Zero-width characters ('\u200b', '\u200c') persist invisibly in text but can unintentionally propagate 
      into external documents or applications when copied. This can cause confusion, unexpected artifacts, or 
      unpredictable behaviors in external programs.

    - Zero-width characters placed immediately before markdown syntax (e.g., '#', '-', '*') can prevent 
      proper markdown rendering, breaking headings, lists, and other formatting elements.

      Examples illustrating markdown formatting disruption:
          "\u200b# HEADER_HERE - will not render correctly"
          "\u200c- BULLET_ITEM - fails to render as list item"

    This is more of an interesting example than a production-ready technique. Use with caution.

author: Justin Kropp
version: 1.0.0
license: MIT
"""

import json, re
from typing import Any, Awaitable, Callable

# Zero-width characters (invisible)
ZERO, ONE = "\u200b", "\u200c"

def encode_invisible(message: str) -> str:
    """Encodes a plain text string into invisible zero-width characters."""
    bits = "".join(f"{ord(c):08b}" for c in message)
    return "".join(ZERO if bit == '0' else ONE for bit in bits)

def decode_invisible(encoded: str) -> str:
    """Decodes invisible zero-width characters back into a plain text string."""
    bits = "".join('0' if ch == ZERO else '1' for ch in encoded if ch in (ZERO, ONE))
    chars = [chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8)]
    return "".join(chars)

def extract_invisible(text: str) -> str:
    """Extract invisible encoded message from visible text."""
    return "".join(ch for ch in text if ch in (ZERO, ONE))

def find_encoded(messages):
    """Searches previous messages for encoded invisible messages."""
    for msg in reversed(messages):
        content = msg.get('content', '')
        if content:
            hidden = extract_invisible(content)
            if hidden:
                try:
                    return decode_invisible(hidden)
                except:
                    continue
    return None

class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None,
        __event_call__: Callable[[dict[str, Any]], Awaitable[None]] | None,
        *__,
    ):
        previous_messages = body.get('messages', [])
        decoded_message = find_encoded(previous_messages)

        if decoded_message:
            yield f"🔓 **Decoded Message:** '{decoded_message}'"
        else:
            user_input = await __event_call__(
                {
                    "type": "input",
                    "data": {
                        "title": "Enter a secret message",
                        "message": "Type something you'd like to hide invisibly.",
                        "placeholder": "Your hidden message...",
                    },
                }
            )

            if user_input:
                invisible_encoded = encode_invisible(user_input)
                yield f"✨ Your message has been encoded invisibly in this response. Please send another message to decode it.{invisible_encoded}"
            else:
                yield "⚠️ No message provided!"
