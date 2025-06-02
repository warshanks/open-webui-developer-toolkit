# Filters Guide

Filters are lightweight plugins that run before, during and after a pipe. Each file can define `inlet`, `stream` and `outlet` handlers to modify chat data or emit events.

## Basic Structure

```python
from pydantic import BaseModel

class Filter:
    class Valves(BaseModel):
        priority: int = 0

    async def inlet(self, body):
        return body

    async def stream(self, event):
        return event

    async def outlet(self, body):
        return body
```

Only the methods you implement are called. `priority` controls execution order when multiple filters are active.

## Loading

Upload the file via the Functions API. Optional packages can be listed in a frontmatter block and will be installed automatically:

```python
"""
requirements: httpx
"""
```

The loader caches each module under `request.app.state.FUNCTIONS`.

## Valves and User Settings

Filters may expose extra options via `Valves` and `UserValves` classes. These are hydrated from the database on each call so settings can be tweaked without re-uploading the code.

Set `file_handler = True` if the filter consumes uploaded files itself. Only parameters declared in a handler's signature are provided (e.g. `body`, `event`, `__user__`).

See `external/FILTER_GUIDE.md` for deeper middleware notes and additional examples.

## Example filters

- `web_search_toggle_filter.py` – enable web search with a toggle.
- `create_image_filter.py` – inject the `image_generation` tool with configurable `SIZE` and `QUALITY` valves.
- `reason_filter.py` – temporarily route a request to another model.
