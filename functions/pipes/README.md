# Writing **Pipes** for Open WebUI  
*A beginner-friendly guide*

---

## Table of Contents
1. [What Is a Pipe?](#what-is-a-pipe)
2. [Hello-World Pipe (Quick Start)](#hello-world-pipe-quick-start)
3. [Anatomy of a Pipe](#anatomy-of-a-pipe)  
   3.1 [Metadata Block](#metadata-block)  
   3.2 [The `Pipe` Class](#the-pipe-class)  
   3.3 [Where to Save & Map Files](#where-to-save--map-files)
4. [Execution Lifecycle](#execution-lifecycle)
5. [Parameter Injection & Special Arguments](#parameter-injection--special-arguments)  
   5.1 [Built-in Injectables](#built-in-injectables)  
   5.2 [`__metadata__` & `__request__`](#metadata--request)  
   5.3 [EventEmitter Patterns](#eventemitter-patterns)
6. [Valves & UserValves](#valves--uservalves)  
   6.1 [Declaring Models](#declaring-models)  
   6.2 [Editing via API / UI](#editing-via-api--ui)
7. [Streaming Replies](#streaming-replies)
8. [Calling Tools from a Pipe](#calling-tools-from-a-pipe)
9. [Manifold (Multi-Pipe) Files](#manifold-multi-pipe-files)
10. [Testing & Debugging](#testing--debugging)  
    10.1 [Unit-Test Template](#unit-test-template)  
    10.2 [Live-Reload Tips](#live-reload-tips)  
    10.3 [Troubleshooting Checklist](#troubleshooting-checklist)
11. [Example Gallery](#example-gallery)
12. [Glossary](#glossary)
13. [TODO / Future Research](#todo--future-research)

---

## What Is a Pipe? <a id="what-is-a-pipe"></a>

A **Pipe** is a single Python file that **generates the assistant’s text** (or
binary) reply for a chat model.  
You can proxy an external LLM, stitch together APIs, or inject custom business logic before the answer reaches the
user.

At runtime Open WebUI:

1. Imports your file,
2. Instantiates `Pipe()`,
3. Calls `Pipe.pipe(body, …extras…)`,
4. Streams the return value back to the chat UI.

Any *filters* run **before** your pipe, so most pipes focus purely on crafting
the response.

---

## Hello-World Pipe (Quick Start) <a id="hello-world-pipe-quick-start"></a>

```python
# functions/pipes/echo.py
class Pipe:
    async def pipe(self, body: dict) -> str:
        # Echo the last user message
        return body["messages"][-1]["content"]
````

1. Save under `functions/pipes/`.
2. In WebUI → **Workspace ▸ Models ▸ “Add Model”** choose *Custom Pipe* and
   point it at `echo.py`.
3. Open chat, select the new model, say “Hi” → it echoes back.

> **Why `async`?** Even if you don’t await anything now, making it `async`
> keeps the door open for streaming or I/O later.

---

## Anatomy of a Pipe <a id="anatomy-of-a-pipe"></a>

### Metadata Block <a id="metadata-block"></a>

Optional docstring at the **top**:

```python
"""
author: Jane Dev
version: 0.2.0
requirements: httpx~=0.27
id: demo_pipe
"""
```

* `requirements` → auto-installed on first import.
* `id` → referenced by filters & testing helpers.

---

### The `Pipe` Class <a id="the-pipe-class"></a>

```python
class Pipe:
    async def pipe(
        self,
        body: dict,
        __messages__: list | None = None,   # alias for body["messages"]
        __event_emitter__=None,             # push UI events
        valves=None,                        # Valves model instance
        __user__=None                       # includes UserValves
    ):
        """Return *anything* JSON-serialisable or a streaming generator."""
        ...
```

Return types accepted:

| Type                           | Behaviour                              |
| ------------------------------ | -------------------------------------- |
| `str` / `dict`                 | Sent as one chunk.                     |
| `AsyncGenerator` / `Generator` | Each `yield` becomes a streamed token. |
| `StreamingResponse`            | Passed straight through.               |

---

### Where to Save & Map Files <a id="where-to-save--map-files"></a>

| Location                                                | Purpose                                |
| ------------------------------------------------------- | -------------------------------------- |
| `functions/pipes/`                                      | Local, version-controlled pipes.       |
| `external/open-webui/backend/open_webui/pipes_builtin/` | Upstream defaults—look but don’t edit. |

Map a model to your file via **Models ▸ Add** or programmatically with:

```bash
POST /api/models
{ "id": "my-echo", "provider": "pipe", "file_id": "echo" }
```

---

## Execution Lifecycle <a id="execution-lifecycle"></a>

1. **Import** – `open_webui.utils.plugin.load_function_module_by_id` rewrites
   relative imports, installs deps, loads module.
2. **Cache** – One instance lives in `request.app.state.FUNCTIONS`.
3. **Filter Chain** – All enabled filters mutate `body`.
4. **`pipe()` Call** – Extra params injected.
5. **Stream / Return** – Handled by `generate_function_chat_completion`.

*(See source: `external/open-webui/backend/open_webui/functions.py` ∼ lines 50-320.)*

---

## Parameter Injection & Special Arguments <a id="parameter-injection--special-arguments"></a>

### Built-in Injectables <a id="built-in-injectables"></a>

| Name                | Value                                        |
| ------------------- | -------------------------------------------- |
| `body`              | Raw request body dict.                       |
| `__messages__`      | `body["messages"]`.                          |
| `__metadata__`      | Dict: chat/model IDs, flags, etc.            |
| `__user__`          | Authenticated user object (plus valves).     |
| `valves`            | Instance of your `Valves` Pydantic model.    |
| `__event_emitter__` | Callback for UI events (`type`, `payload`).  |
| `__request__`       | FastAPI `Request` object.                    |
| `__tools__`         | Mapping of loaded tools (`name`→`callable`). |

Unknown param names are ignored, letting you add/remove freely.

---

### `__metadata__` & `__request__` <a id="metadata--request"></a>

`__metadata__` seeds tracing & feature flags.
`__request__` reveals headers, client IP, cookies—use sparingly; pipes should
stay as stateless as possible.

---

### EventEmitter Patterns <a id="eventemitter-patterns"></a>

```python
async def pipe(self, body, __event_emitter__):
    __event_emitter__("status", {"msg": "Thinking…"})
    await asyncio.sleep(0.5)
    __event_emitter__("status", {"msg": "Almost done"})
    return "Done!"
```

Event `type` options: `status`, `message`, `chat:message`, `citation`,
`notification`, `confirmation`, `input`.

---

## Valves & UserValves <a id="valves--uservalves"></a>

### Declaring Models <a id="declaring-models"></a>

```python
from pydantic import BaseModel

class Valves(BaseModel):
    prefix: str = "📣"

class UserValves(BaseModel):
    uppercase: bool = False
```

### Editing via API / UI <a id="editing-via-api--ui"></a>

*Admin* valves:
`PATCH /api/valves/{model_id}` → `{ "prefix": "🔊" }`

*User* valves (per-chat):
`PATCH /api/uservalves/{chat_id}` → `{ "uppercase": true }`

---

## Streaming Replies <a id="streaming-replies"></a>

If the inbound JSON contains `"stream": true` WebUI treats any **iterable** as
Server-Sent Events:

```python
async def pipe(self, body):
    async def gen():
        for word in "Hello streaming world!".split():
            yield word + " "
            await asyncio.sleep(0.05)
    return gen()  # noqa: R504
```

---

## Calling Tools from a Pipe <a id="calling-tools-from-a-pipe"></a>

```python
async def pipe(self, body, __tools__):
    weather = await __tools__["weather"]["callable"](city="Tokyo")
    return f"It’s {weather['temperature_c']}°C in Tokyo."
```

Combine with event streaming for rich, incremental answers.

---

## Manifold (Multi-Pipe) Files <a id="manifold-multi-pipe-files"></a>

Return **multiple** model definitions from one file:

```python
pipes = [
    {"id": "echo-v1", "description": "Simple echo", "class": "Pipe"},
    {"id": "reverse", "description": "Reverse text", "class": "ReversePipe"},
]
```

`functions.py/generate_function_models` expands them at load-time.

---

## Testing & Debugging <a id="testing--debugging"></a>

### Unit-Test Template <a id="unit-test-template"></a>

```python
from importlib import import_module, reload
pipe_mod = reload(import_module("functions.pipes.echo"))
pipe = pipe_mod.Pipe()
body = {"messages": [{"role": "user", "content": "hi"}]}
assert asyncio.run(pipe.pipe(body)) == "hi"
```

### Live-Reload Tips <a id="live-reload-tips"></a>

* Enable **Dev Mode → Auto-Reload** in settings.
* Tail logs: `docker compose logs -f webui | grep PIPE_ID`.

### Troubleshooting Checklist <a id="troubleshooting-checklist"></a>

* “Model not found”: Did you add it under **Models** and pick the right file?
* ImportError: Check `requirements:` spelling; pip installs on demand.
* Duplicate async loops: Return a single generator, not `async for` inside.

---

## Example Gallery <a id="example-gallery"></a>

| File                | Demonstrates                                  |
| ------------------- | --------------------------------------------- |
| `echo.py`           | Minimal async pipe                            |
| `openai_proxy.py`   | Forward payloads to OpenAI `chat.completions` |
| `weather_stream.py` | Streaming + tool invocation                   |
| `multi_pipe.py`     | Manifold definition                           |

All live under `functions/pipes/examples/`.

---

## Glossary <a id="glossary"></a>

| Term             | Meaning                                                     |
| ---------------- | ----------------------------------------------------------- |
| **Pipe**         | Custom backend that returns the assistant’s reply.          |
| **Filter**       | Pre-processing hook mutating the chat body before the pipe. |
| **Valves**       | Admin-level config persisted in DB.                         |
| **UserValves**   | Per-user/per-chat preferences.                              |
| **EventEmitter** | Pushes live UI events (status, notifications, etc.).        |

---

## TODO / Future Research <a id="todo--future-research"></a>

* **Authentication Strategies** – signed URLs, user tokens, tenant routing.
* **Advanced Streaming Patterns** – detokenisation, per-chunk function calls.
* **Resilience** – retries, exponential backoff helpers, circuit breakers.
* **Observability** – OpenTelemetry traces around `pipe()` and tools.
* **Auto-generated SDK** – scaffold a new pipe via `npx create-webui-pipe`.

---
