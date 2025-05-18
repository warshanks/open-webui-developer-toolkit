# Writing Pipes

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Anatomy of a Pipe](#anatomy-of-a-pipe)
  - [Frontmatter](#frontmatter)
  - [The Pipe Class](#the-pipe-class)
- [Loading and Execution](#loading-and-execution)
- [Valve Configuration](#valve-configuration)
  - [Managing Valves via the API](#managing-valves-via-the-api)
- [Automatic Parameter Injection](#automatic-parameter-injection)
  - [Example Usage](#example-usage)
  - [Understanding `__metadata__`](#understanding-metadata)
  - [Working with `__request__`](#working-with-request)
- [Streaming and Return Values](#streaming-and-return-values)
- [Invoking Tools](#invoking-tools)
- [Manifold Pipes](#manifold-pipes)
- [Using Internal WebUI Functions](#using-internal-webui-functions)
- [Additional Examples](#additional-examples)
- [Future Research](#future-research)

## Overview
Pipes plug custom logic or entire model APIs into Open WebUI. A pipe is a single
Python file exposing a `Pipe` class. When a chat model id references your file
Open WebUI loads it and calls `Pipe.pipe()` to generate a reply. Any configured
filters run first so most pipes focus purely on the response logic.

## Quick Start
A minimal pipe echoes the last message:

```python
class Pipe:
    async def pipe(self, body: dict) -> str:
        return body["messages"][-1]["content"]
```

Save the file under `functions/pipes/` and map a chat model to it via the
Functions UI. If you stream results your `pipe()` must be `async`.

## Anatomy of a Pipe
Every pipe follows the same basic structure.

### Frontmatter
Start the file with an optional metadata block. The loader reads it and installs
any packages listed under `requirements`:

```python
"""
requirements: httpx
id: demo_pipe
"""
```

### The Pipe Class
Expose a `Pipe` class with a `pipe()` method. It may be synchronous or async. In
practice async is preferred so you can await APIs or stream tokens.

```python
class Pipe:
    async def pipe(self, body: dict) -> str:
        return "hello"
```

## Loading and Execution
The loader `open_webui.utils.plugin.load_function_module_by_id` rewrites short
imports then executes your file in a temporary module. Instances are cached under
`request.app.state.FUNCTIONS` so subsequent calls reuse the same object. See
`external/open-webui/backend/open_webui/utils/plugin.py` lines 18‑60 and
`external/open-webui/backend/open_webui/functions.py` lines 55‑66 for details.

## Valve Configuration
Pipes can expose persistent settings via `Valves` and `UserValves` pydantic
models. WebUI hydrates these before each run and passes them to your handler.

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

### Managing Valves via the API
Administrators and users can update valve values without modifying the code
using the routes under `routers/functions.py`.

## Automatic Parameter Injection
`generate_function_chat_completion` inspects your function signature and only
passes the extras you ask for. The middleware assembles an `extra_params`
dictionary which includes metadata, user info and tools. Unknown parameters are
silently ignored.

### Example Usage

```python
class Pipe:
    async def pipe(self, body, __messages__, __event_emitter__):
        last = __messages__[-1]["content"]
        __event_emitter__("log", {"msg": last})
        return last
```

### Understanding `__metadata__`
`__metadata__` combines identifiers and feature flags for the current request.
It originates in `main.py` and flows through the middleware before hitting your
pipe.

### Working with `__request__`
The `__request__` argument exposes the underlying FastAPI `Request` object. Use
it to inspect headers or query parameters.

## Streaming and Return Values
When `stream=True`, `generate_function_chat_completion` treats your return value
as a server-sent event stream. Strings, generators and `StreamingResponse` are
handled transparently. See `functions.py` lines 263‑307.

## Invoking Tools
Tools are provided via the `__tools__` mapping. Call `__tools__[name]["callable"]`
to execute a tool. See `tools/README.md` for details.

## Manifold Pipes
Define a `pipes` attribute returning a list of sub-pipe definitions to expose
multiple models from one file. `generate_function_models` in `functions.py`
processes these entries.

## Using Internal WebUI Functions
For advanced scenarios you can import helpers from the `open_webui` package.
`open_webui.utils.chat.generate_chat_completion` runs the standard chat pipeline
and accepts the same parameters used internally.

## Additional Examples
TODO: add real-world sample pipes demonstrating tool calls and streaming.

## Future Research
TODO: document authentication strategies and advanced streaming patterns.
