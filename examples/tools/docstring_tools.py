"""
title: Docstring Tools
id: docstring_tools
description: Generate tool specs from function docstrings.
author: open-webui
license: MIT
version: 0.0.0
"""

from __future__ import annotations

import inspect
from typing import get_type_hints, Any

from pydantic import BaseModel


def _spec_from_function(fn: Any) -> dict:
    """Build a tool spec from ``fn``'s signature and docstring."""
    hints = get_type_hints(fn)
    doc = inspect.getdoc(fn) or ""
    desc = doc.splitlines()[0] if doc else fn.__name__
    params = {
        name: {"type": "string", "description": hints.get(name, str).__name__}
        for name in hints
        if name != "return"
    }
    return {
        "name": fn.__name__,
        "description": desc,
        "parameters": {"type": "object", "properties": params},
    }


class Tool:
    class Valves(BaseModel):
        pass

    async def echo(self, text: str) -> str:
        """Echo back ``text``."""
        return text

    async def add(self, a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    specs = [_spec_from_function(echo), _spec_from_function(add)]
