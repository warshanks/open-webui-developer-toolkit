"""
title: Message Persistence Probe
id: message_persistence_probe
description: Minimal example pipe used for import tests.
version: 0.1.0
license: MIT
"""

from __future__ import annotations

from typing import Any, AsyncGenerator


class Pipe:
    async def pipe(self, *_, **__) -> AsyncGenerator[Any, None]:
        yield ""
