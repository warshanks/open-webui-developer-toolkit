# Tools Guide

Standalone tools expose functionality that pipes can call. A tool is a single
Python file with a `spec` describing the function and an `invoke()` function that
executes it.

```python
spec = {
    "name": "hello_world",
    "description": "Return a friendly greeting",
    "parameters": {"type": "object", "properties": {}}
}

async def invoke(args: dict) -> str:
    return "hello"
```

Pipes register tools so they can be called using Open WebUI's native tool system.
Place new tool modules in this folder.
