"""
title: Inline-Citation PoC
id: inline_citation_poc
author: OpenAI Codex
description: Persists function calls, outputs, and reasoning via citation metadata.
version: 0.1.0
license: MIT
"""
from __future__ import annotations

import asyncio, datetime, json
from typing import Any, AsyncGenerator, Awaitable, Callable

class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None,
        __metadata__: dict[str, Any] | None = None,
        *_,
    ) -> AsyncGenerator[str, None]:
        """
        Proof-of-concept: store “special” response items in citation metadata
        instead of hidden zero-width tokens.
        """

        # ───────── mock “LLM” output (in real life you’d read from model stream) ─────────
        llm_events = [
            # 1️⃣ encrypted reasoning
            {
                "type": "reasoning",
                "encrypted_content": "[ENCRYPTED_TOKEN_BLOB]",
            },
            # 2️⃣ function call
            {
                "type": "function_call",
                "id": "fc_abc",
                "call_id": "call_drive_time",
                "name": "calculator",
                "arguments": {"expression": "2790/60"},
                "status": "completed",
            },
            # 3️⃣ function call output
            {
                "type": "function_call_output",
                "call_id": "call_drive_time",
                "output": "2790/60 = 46.5 hours",
            },
            # 4️⃣ assistant message chunks (two chunks for demo)
            {"type": "text", "delta": "Certainly! "},
            {"type": "text", "delta": (
                "At 60 mph the trip takes about 46.5 h [1]. "
                "AAA recommends breaks every two hours [2] and NHTSA says rest well beforehand [3]."
            )},
        ]

        # ───────── prepare citation templates ─────────
        # They’ll be populated as events arrive.
        source_map: dict[str, dict[str, Any]] = {
            "[1]": {
                "source": {"name": "Tool Call"},
                "document": [],
                "metadata": [],
            },
            "[2]": {
                "source": {"name": "American Automobile Association (AAA)"},
                "document": [
                    "Take a break every two hours.",
                    "Stop at least every 100 miles to stretch."
                ],
                "metadata": [{
                    "source": "https://www.aaa.com/safety-tips",
                    "date_accessed": datetime.date.today().isoformat(),
                }],
            },
            "[3]": {
                "source": {"name": "NHTSA"},
                "document": [
                    "Get enough rest and avoid midnight-6 a.m. driving."
                ],
                "metadata": [{
                    "source": "https://www.nhtsa.gov/road-safety",
                    "date_accessed": datetime.date.today().isoformat(),
                }],
            },
        }

        assembled_text = ""   # message we stream to the UI

        # ───────── stream / emit ─────────
        for ev in llm_events:
            etype = ev["type"]

            # ❶ REASONING → add invisible metadata under [1]
            if etype == "reasoning":
                source_map["[1]"]["metadata"].append({
                    "payload": ev,           # raw JSON blob
                    "timestamp": datetime.datetime.now().isoformat(),
                })
                continue

            # ❷ FUNCTION CALL
            if etype == "function_call":
                source_map["[1]"]["document"].append(
                    f"Calculator called with {json.dumps(ev['arguments'])}."
                )
                source_map["[1]"]["metadata"].append({"payload": ev})
                continue

            # ❸ FUNCTION OUTPUT
            if etype == "function_call_output":
                source_map["[1]"]["document"].append(f"Calculator returned: {ev['output']}.")
                source_map["[1]"]["metadata"].append({"payload": ev})
                continue

            # ❹ TEXT DELTA → stream word-by-word
            if etype == "text":
                for tk in ev["delta"].split():
                    assembled_text += tk + " "
                    yield tk + " "
                    await asyncio.sleep(0.03)
                continue

        # ───────── final citation dump ─────────
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "chat:completion",
                    "data": {
                        "content": "",                   # keep streamed text
                        "sources": list(source_map.values()),
                    },
                }
            )
