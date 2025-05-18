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

## Events and callbacks

Tools may send updates to the browser while running. Two helpers are injected
when the tool requests them in its signature:

- `__event_emitter__` – fire-and-forget messages to the UI.
- `__event_call__` – display a dialog and wait for a response.

```python
async def example_tool(__event_emitter__, __event_call__):
    await __event_emitter__({
        "type": "status",
        "data": {"description": "Loading", "done": False},
    })
    ok = await __event_call__({
        "type": "confirmation",
        "data": {"title": "Continue?", "message": "Run step?"},
    })
    if ok:
        await __event_emitter__({
            "type": "replace",
            "data": {"content": "step complete"},
        })
```

`__event_call__` can also run JavaScript (`execute`) or prompt the user for text
(`input`). The emitter supports `message`, `replace`, `status`, `citation` and
`notification` event types. See the removed `event_emitter_example.py` for a
full demonstration.
