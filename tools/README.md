# Tools Guide

Standalone tools expose additional functionality that pipes can call. Each tool
is a **single Python file** containing a `Tools` class. Every method of the
class becomes an individual tool. Open WebUI loads these modules through
`plugin.load_tool_module_by_id` and builds the OpenAI style specs
automatically.

This folder complements the guides for [pipes](../functions/pipes/README.md) and
[filters](../functions/filters/README.md). A tool provides standalone functions
that a pipe can invoke during a chat request.

```python
"""
requirements: httpx
"""

class Tools:
    def hello(self, name: str):
        """Return a friendly greeting.

        :param name: User name
        """
        return {"message": f"Hello {name}"}
```

When a file is uploaded via the admin UI the loader installs any packages listed
in the optional **frontmatter** block (`requirements:` in the example above).
Short import paths such as `from utils.chat` are rewritten to `open_webui.utils`
so the module can reuse helpers from the main project.

### Frontmatter and upload

Each tool file begins with a triple quoted block. At minimum declare an `id:` so
WebUI can store and update the tool. Additional keys like `requirements:` list
extra packages that are installed before the code runs. The loader parses this
header and rewrites short imports before executing the module in a temporary
file【F:external/PLUGIN_GUIDE.md†L5-L29】.

Use `.scripts/publish_to_webui.py` to upload a tool via the API. The script
extracts the `id:` and description from the header and sends the file to a
running WebUI instance.

## How tools are discovered

`backend/open_webui/utils/tools.py` converts each method of the `Tools` class
into an async callable. Type hints and docstrings are parsed using
`convert_function_to_pydantic_model` and then transformed to an OpenAI spec with
`convert_pydantic_model_to_openai_function_spec`【F:external/TOOLS_GUIDE.md†L3-L10】【F:external/TOOLS_GUIDE.md†L30-L51】.
`get_tools()` returns a dictionary mapping the method name to its callable and
metadata such as the generated spec【F:external/TOOLS_GUIDE.md†L12-L28】.

Tools may expose two optional Pydantic models named `Valves` and `UserValves`
for configuration. The loader hydrates these models with values stored in the
database before every call. This allows administrators to define global defaults
while users can override selected fields.

If a module defines `file_handler = True` the middleware removes uploaded files
from the payload after the tool runs because the tool manages them itself.

### Parameter injection

`get_tools()` passes extra context to tool functions. Only the parameters
declared in the function signature are provided. Useful names mirror those
available to pipes and filters and include:

- `__event_emitter__` / `__event_call__`
- `__user__`
- `__metadata__`
- `__request__`
- `__model__`
- `__messages__`
- `__files__`

These values come from the chat middleware and allow a tool to inspect the
conversation or emit events【F:functions/pipes/README.md†L66-L78】.

## Calling tools from a pipe

Pipes receive a mapping of registered tools via the `__tools__` parameter. Each
entry exposes a `callable` and a `spec` describing the parameters. A pipe can
invoke a tool directly:

```python
async def pipe(self, body, __tools__):
    add = __tools__["add"]["callable"]
    result = await add(a=1, b=2)
    return str(result)
```

Remote **tool servers** are also supported. When a tool id starts with
`server:` the loader fetches an OpenAPI document, converts each `operationId`
into a tool payload and proxies the call via `execute_tool_server`【F:external/TOOLS_GUIDE.md†L53-L79】.

## Events and callbacks

Tools may interact with the browser while running. Two helpers can be requested
in a tool function's signature:

- `__event_emitter__` – fire-and-forget messages such as status updates.
- `__event_call__` – display a dialog and wait for the user's response.

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

`__event_call__` can also run JavaScript (`execute`) or prompt for text
(`input`). The emitter supports `message`, `replace`, `status`, `citation` and
`notification` event types.
