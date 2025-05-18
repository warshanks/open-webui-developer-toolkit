# Pipes Guide

A **pipe** is a single Python file that exposes a `Pipe` class. Open WebUI loads
these modules dynamically and executes the pipe when a user selects it as a chat
model.

```python
# minimal pipe structure
class Pipe:
    async def pipe(self, chat_id: str, message: str) -> str:
        return "response"
```

Pipes may call external APIs, emit new chat messages and manage their own state.
To add a new pipe place the file here and ensure it defines a `Pipe` class with
an async `pipe()` method.

## Loading custom pipes

`backend/open_webui/utils/plugin.py` retrieves each file, rewrites short imports
and executes it in a temporary module. A triple quoted *frontmatter* block at
the top is parsed so dependencies can be installed automatically:

```python
"""
requirements: httpx, numpy
"""
```

If the module exposes `Pipe`, the loader returns an instance.

### Frontmatter fields

The frontmatter may contain any key/value pairs. The `requirements` list is
installed with `pip` before the pipe runs. Other fields are available as
metadata.

### Valves

A pipe can define `Valves` and `UserValves` classes to expose adjustable
settings. Values are stored by the server and injected on each call:

```python
from pydantic import BaseModel

class Valves(BaseModel):
    prefix: str = ">>"

class UserValves(BaseModel):
    shout: bool = False

class Pipe:
    def pipe(self, body, __user__, valves):
        msg = body["messages"][-1]["content"]
        if __user__.valves.shout:
            msg = msg.upper()
        return f"{valves.prefix} {msg}"
```

The server exposes endpoints to update these values without re-uploading the
code.

## Parameter injection

`functions.py` inspects the `pipe` signature and only passes the arguments it
requests. Useful values include:

- `__event_emitter__` / `__event_call__` – communicate with the browser
- `__chat_id__`, `__session_id__`, `__message_id__` – conversation identifiers
- `__files__` – uploaded files
- `__user__` – user info and optional `UserValves`
- `__tools__` – mapping of registered tools
- `__messages__` – raw message history

Extra context can be passed using the same names.

## Invoking tools from a pipe

Tools are provided through the `__tools__` dictionary and can be called
directly:

```python
class Pipe:
    async def pipe(self, body, __tools__):
        add = __tools__["add"]["callable"]
        result = await add(a=1, b=2)
        return str(result)
```

`utils.tools.get_tools` converts each tool into a callable and exposes its spec.

## Pipe lifecycle

Pipes are cached in `request.app.state.FUNCTIONS` and loaded only once per
server process. Valve values are hydrated before each execution:

```python
pipe = function_module.pipe
params = get_function_params(function_module, form_data, user, extra_params)
res = await execute_pipe(pipe, params)
```

Reload the server or update the valves to pick up changes.
