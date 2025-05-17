"""
title: Tool Template
id: tool_template
description: Minimal example tool.
author: suurt8ll
author_url: https://github.com/suurt8ll
funding_url: https://github.com/suurt8ll/open_webui_functions
license: MIT
version: 0.0.0
requirements:
"""

from pydantic import BaseModel, Field


class Tool:
    class Valves(BaseModel):
        pass

    class Input(BaseModel):
        text: str = Field(..., description="Text to echo back")

    specs = [
        {
            "name": "echo",
            "description": "Return the provided text.",
            "parameters": Input.model_json_schema(),
        }
    ]

    def __init__(self):
        self.valves = self.Valves()
        print(f"{[__name__]} Tool has been initialized.")

    async def echo(self, text: str) -> str:
        """Return the provided text."""
        print(f"{[__name__]} echo called with: {text}")
        return text
