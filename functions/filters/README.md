# Filters

Each filter lives inside its own folder. The folder name matches the filter title and includes:

- `README.md` – short description and usage notes
- `CHANGELOG.md` – recorded history following Keep a Changelog
- `<filter>.py` – the filter implementation

Upload the Python file via the Functions API to install. Example filters include:

- `web_search_toggle_filter`
- `create_image_toggle_filter`
- `reason_toggle_filter`
- `debug_toggle_filter`

The rest of this document explains the general filter structure.

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

Only the methods you implement are called. `priority` controls execution order when multiple filters are active. Upload optional dependencies via a frontmatter block:

```python
"""
requirements: httpx
"""
```

Filters may expose user-tweakable options via `Valves` and `UserValves` classes. Set `file_handler = True` if the filter consumes uploaded files itself. See `external/FILTER_GUIDE.md` for advanced notes.
