# Filters Guide

Filters are lightweight plugins that run **alongside pipes**.  They intercept chat
traffic at three points – before a request hits the model, while the model streams
tokens and once the full response is produced.  Picture the pipeline as a stream of
water: each filter is a treatment step that can enrich, sanitise or log the flow
without replacing the underlying pipe.  Filters are stored as single Python files
and the loader invokes whichever handlers they implement.

Filter IDs are resolved by `get_sorted_filter_ids`, which merges globally enabled
filters with those declared on a model and sorts them by `Valves.priority`.

## How Filters Fit in the Pipeline

1. **inlet** – runs on the request body before the pipe executes. Use it to add
   context, scrub data or block unwanted content.
2. **pipe** – generates the assistant reply (not covered here).
3. **stream** – intercepts each chunk of the assistant's reply while streaming.
4. **outlet** – processes the full response payload once the pipe is done.

By chaining multiple filters you can shape the conversation without modifying the
underlying pipe logic.

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

Filter files live in the database and are fetched on demand.
`utils.plugin.load_function_module_by_id` rewrites short import paths (e.g.
`from utils.chat` → `from open_webui.utils.chat`), installs any packages listed
in a triple quoted **frontmatter** block and executes the file. If the module
exposes `Filter`, the resulting object is cached under
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

`process_filter_functions` retrieves the module from
`request.app.state.FUNCTIONS` if it has been loaded previously and only then
executes the appropriate handler. When the handler is synchronous it runs
directly; otherwise it is awaited.

## Parameter injection

`process_filter_functions` inspects each handler's signature with
`inspect.signature` and only supplies the parameters it explicitly declares. The
following names are commonly available:

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

## Middleware integration

`process_chat_payload` in the WebUI middleware builds the `extra_params`
dictionary containing event callbacks, user info and metadata.  This dictionary
is passed to `process_filter_functions` so every filter can access the same
helpers that pipes do.  Filters execute before the selected pipe runs and again
while streaming tokens back to the client.  See
`external/MIDDLEWARE_GUIDE.md` for a deeper walkthrough of the request flow.

## Filter lifecycle

1. `get_sorted_filter_ids` merges globally enabled functions with the
   model's `meta.filterIds` list and sorts them by `Valves.priority`. Only
   functions that are marked active are returned.
2. Each filter module is loaded (or reused from
   `request.app.state.FUNCTIONS`) and its handler method is invoked via
   `process_filter_functions`.
3. Valves and per‑user settings are hydrated before the call and only the
   parameters declared in the method signature are passed.
4. When `file_handler` is true the middleware removes `files` from the payload
   after the `inlet` call so the filter can process them itself.

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

Other patterns include adding system context or formatting the assistant reply:

```python
class Filter:
    def inlet(self, body: dict) -> dict:
        body.setdefault("messages", []).insert(
            0, {"role": "system", "content": "You are a helpful assistant."}
        )
        return body

    def outlet(self, body: dict) -> dict:
        for msg in body.get("messages", []):
            if msg.get("role") == "assistant":
                msg["content"] = f"**{msg['content']}**"
        return body
```

### Toggle Filter Example (Open WebUI 0.6.10)

Filters may show a switch in the UI and a custom icon when `toggle` and `icon`
are defined. The example below emits a status toast when toggled:

```python
from pydantic import BaseModel
from typing import Optional

class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # adds a UI switch
        # small SVG encoded as a data URI
        self.icon = "data:image/svg+xml;base64,..."

    async def inlet(
        self, body: dict, __event_emitter__, __user__: Optional[dict] = None
    ) -> dict:
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Toggled!",
                    "done": True,
                    "hidden": False,
                },
            }
        )
        return body
```

A screenshot of the toggle in action can be found [here](https://docs.openwebui.com/assets/images/toggle-filter-491e8306ef6b94f72cd5236c7944043d.png).

More implementation details and code snippets can be found in
`external/FILTER_GUIDE.md` which summarises the upstream
`open_webui.utils.filter` module.
