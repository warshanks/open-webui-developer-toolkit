# Pipes Guide

A **pipe** is a single Python file exposing a `Pipe` class. When a chat model id points to that file, Open WebUI loads the module and executes `Pipe.pipe()` to generate the assistant reply. Requests travel through any configured filters first so a pipe usually only implements the core response logic.

```python
# minimal pipe structure
class Pipe:
    async def pipe(self, body: dict) -> str:
        return "response"
```

Pipes may call external APIs, emit additional chat messages and hold state between calls. Add new pipes under this folder and ensure the class defines a `pipe()` method. The method can be synchronous or `async`; both styles work, but async functions are required when streaming results.

## Loading custom pipes

The loader at `backend/open_webui/utils/plugin.py` reads the file, rewrites
short imports such as `from utils.chat` to `open_webui.utils.chat` and
executes the content in a temporary module【F:external/PLUGIN_GUIDE.md†L18-L41】.
The **frontmatter** block must be the first thing in the file – the parser only
recognises it when the very first line contains `"""`. Use this header to store
metadata and optional dependencies:

```python
"""
requirements: httpx, numpy
id: demo_pipe
"""
```

`install_frontmatter_requirements` installs the `requirements` list before the pipe runs. Other fields are stored as metadata.

If the executed module exposes `Pipe`, the loader returns an instance and caches it in `request.app.state.FUNCTIONS` for reuse【F:external/open-webui/backend/open_webui/functions.py†L60-L66】.

### Valves

A pipe can define `Valves` and `UserValves` Pydantic models to expose adjustable settings. The server stores these values and injects them on each call:

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

Valve values can be updated via the Functions API without re-uploading the code.

## Parameter injection

`generate_function_chat_completion` inspects the `pipe` signature and only
supplies the parameters it explicitly declares.  Internally the helper calls
`inspect.signature` inside `get_function_params` and builds a dictionary of
arguments that exist in the function signature:

```python
sig = inspect.signature(function_module.pipe)
params = {"body": form_data} | {
    k: v for k, v in extra_params.items() if k in sig.parameters
}
```

Because of this opt-in behaviour you may freely upgrade Open WebUI without
breaking old extensions—new context parameters are ignored unless you declare
them in your function signature.  The available extras mirror the values added
to `extra_params` inside `generate_function_chat_completion`【F:external/open-webui/backend/open_webui/functions.py†L204-L238】.

Any name not present in `sig.parameters` is silently discarded so a pipe can
opt‑in to the context it needs without worrying about new parameters appearing
later【F:external/open-webui/backend/open_webui/functions.py†L178-L188】.  The
`extra_params` dictionary is assembled from the request metadata and user
information before this step.  Common values include:

| Name | Purpose |
|------|---------|
|`__event_emitter__`, `__event_call__`| communicate with the browser via websockets |
|`__chat_id__`, `__session_id__`, `__message_id__`| identify the active conversation |
|`__files__`| uploaded files for the request |
|`__user__`| user data and optional `UserValves` settings |
|`__tools__`| mapping of registered tools |
|`__messages__`| raw message history |
|`__model__`| current model definition |
|`__metadata__`| metadata dictionary attached to the request |
|`__task__`, `__task_body__`| background task info |
|`__id__`| sub‑pipe id when using manifolds |
|`__request__`| the FastAPI `Request` object |

When the pipe defines a `UserValves` model the `__user__` dictionary gains a
`valves` field populated from the database.  This lets you store per-user
configuration without changing the function signature.  Valve values are looked
up via `Functions.get_user_valves_by_id_and_user_id` during parameter
construction.

`generate_function_chat_completion` assembles these extras using information
from the request and user. The `process_chat_payload` middleware prepares the
initial `extra_params` dictionary before the pipe runs so every extension sees
the same context【F:external/MIDDLEWARE_GUIDE.md†L98-L111】. Event callbacks and
tool contexts are only set up when `chat_id`, `session_id` and `message_id` are
present. See lines 200‑251 of `functions.py` for the full logic
【F:external/open-webui/backend/open_webui/functions.py†L200-L251】.

### Streaming and return values

When `stream=True` the middleware treats the output of `pipe()` as a server-sent event stream. `generate_function_chat_completion` handles several cases:

- returning a `StreamingResponse` proxies its body iterator directly;
- yielding strings or `data:` lines from a generator produces streamed chunks;
- returning a plain string sends one chunk followed by `[DONE]`.

Relevant logic appears around lines 267‑307 of `functions.py`【F:external/open-webui/backend/open_webui/functions.py†L267-L307】. For non streaming requests the pipe may return a string, a `dict` or any Pydantic model. Dictionaries are forwarded as-is while models are converted using `model_dump()`.

## Invoking tools from a pipe

Tools are provided through the `__tools__` dictionary. Each entry exposes an async `callable` and an OpenAI style `spec`:

```python
class Pipe:
    async def pipe(self, body, __tools__):
        add = __tools__["add"]["callable"]
        result = await add(a=1, b=2)
        return str(result)
```

`get_tools()` builds this mapping and handles valve hydration for tools. See `tools/README.md` for more details.
Remote entries starting with `server:` are generated from OpenAPI specs and
behave like local tools. They are configured through
`TOOL_SERVER_CONNECTIONS` and cached in `app.state.TOOL_SERVERS`.

## Pipe lifecycle

Pipes are loaded once per process and cached. Subsequent requests reuse the same object from `request.app.state.FUNCTIONS`【F:external/open-webui/backend/open_webui/functions.py†L57-L66】. Before each execution valve values and user settings are hydrated and the function parameters are assembled:

```python
pipe = function_module.pipe
params = get_function_params(function_module, form_data, user, extra_params)
res = await execute_pipe(pipe, params)
```

Reload the server or update valve settings to pick up changes.

## Manifold pipes

A single file can expose multiple sub‑pipes by defining a `pipes` attribute. This can be a list or a callable (sync or async) returning that list. `generate_function_models` iterates over these values to build the model list【F:external/open-webui/backend/open_webui/functions.py†L72-L110】. Each entry describes an additional model shown in the UI:

```python
class Pipe:
    name = "demo:"

    def pipes(self):
        return [
            {"id": "fast", "name": "Fast mode"},
            {"id": "slow", "name": "Slow mode"},
        ]

    async def pipe(self, body, __id__):
        if __id__.endswith("fast"):
            return "fast reply"
        return "slow reply"
```

Selecting `demo:fast` or `demo:slow` calls the same module with the id suffix. Inspect `__id__` in the handler to adapt behaviour.
