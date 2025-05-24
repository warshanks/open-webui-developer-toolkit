# Events: `__event_emitter__` and `__event_call__`

Open WebUI extensions can push real-time updates to the UI.  Each Tool or Pipe receives two async helpers:

* `__event_emitter__` – fire-and-forget events
* `__event_call__` – events that wait for user input

Both helpers expect a dictionary `{"type": str, "data": dict}`.  `__event_call__` returns the user's response when applicable.

## Common event types

| type                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `status`            | Progress or activity updates                          |
| `chat:message:delta`| Append streamed text to the current message           |
| `chat:message`      | Replace the current message content                   |
| `chat:message:files`| Attach or update message files                        |
| `chat:title`        | Update the conversation title                         |
| `chat:tags`         | Update conversation tags                              |
| `source`/`citation` | Add a citation or code execution result               |
| `notification`      | Show a toast notification                             |
| `confirmation`      | Ask for confirmation (requires `__event_call__`)      |
| `input`             | Request simple user input (requires `__event_call__`) |
| `execute`           | Run code client-side (requires `__event_call__`)      |

Custom event types may be used if the frontend knows how to handle them.

## Examples

Emit a simple status update:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Processing started", "done": False}
})
```

Pause execution until the user confirms:

```python
result = await __event_call__({
    "type": "confirmation",
    "data": {"title": "Are you sure?", "message": "Proceed with action?"}
})
```

`result` will contain the user's answer or input value.
