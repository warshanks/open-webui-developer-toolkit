# Custom Pipes

Open WebUI allows administrators to register Python functions as chat models. These **pipes** are loaded dynamically by `backend/open_webui/utils/plugin.py` and executed by `backend/open_webui/functions.py`.

## Loading a pipe

`load_function_module_by_id` reads the source code from the database, rewrites short imports and executes the module inside a temporary namespace. When the module exposes a `class Pipe` instance it is returned to the caller:

```python
if hasattr(module, "Pipe"):
    return module.Pipe(), "pipe", frontmatter
```

Any triple quoted frontmatter block at the start of the file is parsed with `extract_frontmatter` so dependencies can be installed automatically.

## Execution flow

`generate_function_chat_completion` retrieves the pipe and prepares extra parameters such as the current user, associated files and websocket callbacks. These values are only passed if the pipe declares matching arguments:

```python
extra_params = {
    "__event_emitter__": __event_emitter__,
    "__event_call__": __event_call__,
    "__chat_id__": metadata.get("chat_id", None),
    "__session_id__": metadata.get("session_id", None),
    "__message_id__": metadata.get("message_id", None),
    "__task__": __task__,
    "__task_body__": __task_body__,
    "__files__": files,
    "__user__": {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    },
    "__metadata__": metadata,
    "__request__": request,
}
```

If `form_data["stream"]` is truthy the function yields chunks produced by the pipe using `StreamingResponse`. Otherwise it waits for the result and converts it to the OpenAI completion format.

## Creating a pipe

A minimal pipe looks like this:

```python
"""
requirements: requests
"""

class Pipe:
    async def pipe(self, body, __user__, __event_emitter__):
        msg = body["messages"][-1]["content"]
        await __event_emitter__({"type": "log", "data": msg})
        return f"echo: {msg}"
```

Upload the file through the Functions UI and enable it. The `requirements` field ensures `requests` is installed before the module runs.

### Manifold pipes

When a module defines a `pipes` attribute it can act as a **manifold** exposing several models. The attribute can be a list or a function returning a list:

```python
class Pipe:
    name = "translator: "
    pipes = [
        {"id": "en", "name": "English"},
        {"id": "es", "name": "Spanish"},
    ]

    def pipe(self, body, __metadata__):
        lang = __metadata__["model"].split(".")[-1]
        text = body["messages"][-1]["content"]
        return f"[{lang}] {text}"
```

`get_function_models` expands these entries so users can select `pipe_id.sub_id` as a normal model id.

Pipes integrate with filters and tools just like built‑in models, making them a powerful extension mechanism.
