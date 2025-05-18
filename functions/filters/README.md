# Filters Guide

Filters intercept chat traffic at three stages and can mutate the payload or stream events.
Each filter is a single Python file defining a `Filter` class. The loader instantiates
this class and invokes the methods that exist:

```python
class Filter:
    async def inlet(self, body):
        """Optional: run before the pipe."""
        return body

    async def outlet(self, body):
        """Optional: run after the pipe returns."""
        return body

    async def stream(self, event):
        """Optional: inspect each streamed token."""
        return event
```

Only the methods you implement are called. They may be synchronous or `async`.

## Loading and frontmatter

`utils.plugin.load_function_module_by_id` rewrites short imports, installs
packages declared in a triple quoted **frontmatter** block and executes the file.
If the module exposes `Filter`, the instance is cached under
`request.app.state.FUNCTIONS` and reused for later requests.

```python
"""
requirements: httpx
"""
```

The `requirements` list is installed with `pip` before the filter runs. Other
fields are available as metadata.

## Configuration via Valves

Filters may expose adjustable settings by defining `Valves` and `UserValves`
classes. These inherit from `pydantic.BaseModel` and are populated from the
server database on each call:

```python
from pydantic import BaseModel

class Valves(BaseModel):
    priority: int = 0

class UserValves(BaseModel):
    quota: int = 5
```

Values can be updated through the Functions API without re-uploading the code.
`priority` decides the order filters run—the higher the value the later it
executes.

Set `file_handler = True` when the filter consumes uploaded files itself. The
middleware then removes them from the payload.

## Parameter injection

`process_filter_functions` inspects the method signature and only supplies the
parameters it requests. The following names are commonly available:

- `body` – request/response payload for `inlet` and `outlet` methods
- `event` – single streaming event for `stream`
- `__id__` – filter id
- `__event_emitter__` – send updates to the browser
- `__event_call__` – display a dialog and await a response
- `__user__` – current user info and optional `UserValves` instance
- `__metadata__` – chat/session identifiers
- `__request__` – the `fastapi.Request` object
- `__model__` – model data

Extra context can be injected using the same variable names.

## Filter lifecycle

1. Filter ids are gathered from globally enabled functions and the selected
   model's `meta.filterIds` list.
2. They are sorted by `Valves.priority` and loaded if not already cached.
3. Each filter receives hydrated valve values and the extracted parameters.
4. When `file_handler` is true the middleware removes `files` from the payload
   after the `inlet` call.

Filters can raise exceptions to abort the request. Streaming filters can inspect
or modify each token before it reaches the client.

### Example

A filter that enforces a turn limit and logs streamed tokens:

```python
from pydantic import BaseModel

class Valves(BaseModel):
    max_turns: int = 4

class UserValves(BaseModel):
    bonus_turns: int = 0

file_handler = True

class Filter:
    def inlet(self, body, __user__, valves):
        limit = valves.max_turns + __user__.valves.bonus_turns
        if len(body.get("messages", [])) > limit:
            raise Exception(f"Conversation turn limit exceeded ({limit})")
        return body

    async def stream(self, event):
        print("token", event.get("data"))
        return event
```

Place filter modules in this folder. They can be combined with any pipe to
customise the chat pipeline.
