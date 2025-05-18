# Tools Guide

Tools are small Python scripts that give your model superpowers such as web
search, image generation or voice output. Each script defines a `Tools` class
whose methods become individual tools. Methods may be synchronous or `async` –
the loader wraps them so every tool is awaitable. When uploaded the server
executes the file via `plugin.load_tool_module_by_id`, rewriting short imports,
installing any dependencies and building an OpenAI‑style JSON spec so the tools
can be called through function calling.

Typical capabilities include:

- **Web search** for real‑time answers
- **Image generation** from text prompts
- **Voice output** using ElevenLabs or similar services

This folder complements the guides for
[pipes](../functions/pipes/README.md) and
[filters](../functions/filters/README.md). Tools provide standalone functions
that pipes can invoke during a chat request.

## Installing Tools

You can install tools from the **Community Tool Library** or by uploading a
Python file directly. Click *Get* in the library, enter your WebUI address and
use “Import to WebUI”.

**Safety tip:** Only import tools from sources you trust as they execute Python
code on your server.
## Writing a Custom Toolkit

A toolkit lives in a single Python file. Start with a metadata block:

```python
"""
id: string_inverse
title: String Inverse
author: Your Name
author_url: https://website.com
git_url: https://github.com/username/string-reverse.git
description: This tool calculates the inverse of a string
required_open_webui_version: 0.4.0
requirements: langchain-openai, langgraph, ollama, langchain_ollama
version: 0.4.0
licence: MIT
"""
```

Only `id` is required but the extra fields make maintenance easier.

Define a `Tools` class. Each method becomes an individual callable:

```python
class Tools:
    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        api_key: str = Field("", description="Your API key here")

    def reverse_string(self, string: str) -> str:
        """Reverses the input string.

        :param string: The string to reverse
        """
        if self.valves.api_key != "42":
            return "Wrong API key"
        return string[::-1]
```

Type hints are mandatory so the loader can build the JSON schema for function calling. Nested hints such as `list[tuple[str, int]]` also work.

### Valves and UserValves

`Valves` define global settings while `UserValves` allow per-user overrides. The loader hydrates them from the database before each call so administrators can set defaults and users can tweak values【F:external/FILTER_GUIDE.md†L120-L145】.


## Using Tools

Tools can be enabled per chat or per model. While chatting click the ➕ icon in
the input box to toggle individual tools. For frequent use open **Workspace ▸
Models**, edit the model and check the tools you want enabled by default.

The optional **AutoTool Filter** can help your LLM pick the right tool when
multiple are available.

### Default vs Native Function Calling

Tools work with any model using a prompt based helper, but models with built in
function calling can choose and chain tools natively. Open WebUI detects this via
the `function_calling` metadata field. When a pipe notices tools but native mode
is disabled it warns the user:

```python
if __tools__ and __metadata__.get("function_calling") != "native":
    await __event_emitter__(
        {
            "type": "chat:completion",
            "data": {
                "content": (
                    "🛑 Tools detected, but native function calling is disabled.\n\n"
                    "To enable tools in this chat, switch Function Calling to 'Native'."
                ),
            },
        }
    )
```

Switch modes from **Chat Controls ▸ Advanced Params**. Native calling is faster
and more reliable when chaining multiple tools, but only works with models that
support the feature.

When a file is uploaded via the admin UI the loader installs any packages listed
in the optional **frontmatter** block (`requirements:` in the example above).
Short import paths such as `from utils.chat` are rewritten to `open_webui.utils`
so the module can reuse helpers from the main project.

### Frontmatter and upload

Each tool file begins with a triple quoted block. At minimum declare an `id:` so
WebUI can store and update the tool. Additional keys such as `requirements:` and
`description:` list extra packages and optional metadata. The loader parses this
header and rewrites short imports before executing the module in a temporary
file【F:external/PLUGIN_GUIDE.md†L5-L29】. A typical header looks like:

```python
"""
id: string_inverse
title: String Inverse
author: Your Name
author_url: https://website.com
git_url: https://github.com/username/string-reverse.git
description: This tool calculates the inverse of a string
required_open_webui_version: 0.4.0
requirements: langchain-openai, langgraph, ollama, langchain_ollama
version: 0.4.0
licence: MIT
"""
```

Only the `id` is mandatory, however declaring `title`, `description` and
`requirements` makes the tool easier to manage. The loader performs these steps
when initializing the module:
1. Retrieve the source from the database (or use uploaded content).
2. Apply `replace_imports` and install `requirements`.
3. Write the code to a temporary file so `__file__` points to a real path.
4. `exec` the module and return the instantiated `Tools` object
   【F:external/PLUGIN_GUIDE.md†L33-L59】.

Use `.scripts/publish_to_webui.py` to upload a tool via the API. The script
extracts the `id:` and description from the header, infers the plugin type from
the file path and sends the file to a running WebUI instance.

## How tools are discovered

`backend/open_webui/utils/tools.py` discovers tool methods and exposes them as
async functions. Normal functions are wrapped into coroutines via
`get_async_tool_function_and_apply_extra_params` so every call can be awaited
【F:external/open-webui/backend/open_webui/utils/tools.py†L49-L65】. Each method is inspected with
`convert_function_to_pydantic_model` which turns its signature and docstring into
a Pydantic model. This model is then converted to the OpenAI JSON format via
`convert_pydantic_model_to_openai_function_spec` so LLMs can call the tool
directly【F:external/TOOLS_GUIDE.md†L3-L10】【F:external/TOOLS_GUIDE.md†L30-L51】.
`get_tools()` assembles a dictionary mapping function names to a callable and its
specification ready for the chat pipeline【F:external/TOOLS_GUIDE.md†L12-L28】.

Loaded modules are cached under `request.app.state.TOOLS` so subsequent calls do
not re-import the code. Valve values are hydrated from the database before each
execution.

Tools may expose two optional Pydantic models named `Valves` and `UserValves`
for configuration. The loader hydrates these models with values stored in the
database before every call. This allows administrators to define global defaults
while users can override selected fields.

If a module defines `file_handler = True` the middleware removes uploaded files
from the payload after the tool runs because the tool manages them itself. When
`citation = True` the pipeline treats any returned snippets as citation sources.

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
conversation or emit events. `__event_emitter__` and `__event_call__` interface
with the user's websocket connection so messages can appear in real time.
`__metadata__` contains identifiers such as `chat_id` and
`session_id`【F:functions/pipes/README.md†L66-L78】【F:external/MIDDLEWARE_GUIDE.md†L100-L112】.

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
`server:` the loader fetches an OpenAPI document and converts each
`operationId` into a tool definition using `convert_openapi_to_tool_payload`.
Server entries are configured under the `TOOL_SERVER_CONNECTIONS` setting and
may use a Bearer or session token for authentication. The specification is
downloaded once with `get_tool_servers_data` and cached in
`request.app.state.TOOL_SERVERS` so that subsequent requests do not hit the
remote server again【F:external/open-webui/backend/open_webui/routers/tools.py†L38-L45】.
Each OpenAPI operation is exposed as a tool and returned alongside local tools
when calling `GET /tools`【F:external/open-webui/backend/open_webui/routers/tools.py†L48-L71】.
Calls are proxied via `execute_tool_server` so the HTTP API behaves like a local
tool【F:external/TOOLS_GUIDE.md†L53-L79】【F:external/TOOLS_GUIDE.md†L80-L103】.

See [external/TOOLS_GUIDE.md](../external/TOOLS_GUIDE.md) for a deeper look at
the request flow and schema conversion logic.

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
`notification` event types so tools can update the chat UI while running.
