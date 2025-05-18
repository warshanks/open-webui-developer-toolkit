# Tools Guide

Tools are single-file Python modules that teach Open WebUI new actions. Each file defines a `Tools` class whose methods are converted into OpenAI function specs. The loader installs any dependencies and rewrites imports so the code runs inside WebUI.

## Table of Contents
- [Introduction](#introduction)
- [Quick Start](#quick-start)
  - [Hello Tool Example](#hello-tool-example)
  - [Installing Your Tool](#installing-your-tool)
- [Anatomy of a Tool](#anatomy-of-a-tool)
  - [File Layout](#file-layout)
  - [Frontmatter Fields](#frontmatter-fields)
  - [Writing Tool Methods](#writing-tool-methods)
  - [Valves and UserValves](#valves-and-uservalves)
- [Using Tools in WebUI](#using-tools-in-webui)
  - [Enabling Tools](#enabling-tools)
  - [Default vs Native Function Calling](#default-vs-native-function-calling)
  - [Uploading with Frontmatter](#uploading-with-frontmatter)
- [Calling Tools from a Pipe](#calling-tools-from-a-pipe)
- [Internals](#internals)
  - [Tool Discovery](#tool-discovery)
  - [Parameter Injection](#parameter-injection)
  - [Remote Tool Servers](#remote-tool-servers)
  - [Events and Callbacks](#events-and-callbacks)
- [Further Reading](#further-reading)
- [TODO](#todo)
  - [Research Topics](#research-topics)
  - [Example Ideas](#example-ideas)
  - [Documentation Placeholders](#documentation-placeholders)
  - [Field Reference TODO](#field-reference-todo)

## Introduction

Tools teach WebUI new actions. Each Python file exposes a `Tools` class and every
method becomes an OpenAI function definition. The loader reads the method name,
type hints and docstring to create the JSON schema that tells the LLM which
parameters to send.

Typical uses include:

- **Web search** for real-time answers
- **Image generation** from text prompts
- **Voice output** using text-to-speech services

## Quick Start

### Hello Tool Example

Create a file named `hello_tool.py`:

```python
"""
id: hello_tool
"""

class Tools:
    def hello(self, name: str) -> str:
        """Return a friendly greeting."""
        return f"Hello {name}!"
```

Upload the file through the **Community Tool Library** or the API and enable it for your chat. The method will appear as an OpenAI function named `hello`.

### Installing Your Tool

You can install tools from the library or upload a Python file directly. Click *Get* in the library, enter your WebUI address and choose *Import to WebUI*. Only import tools from sources you trust as they execute Python code on your server.

## Anatomy of a Tool

### File Layout

Each tool file begins with a frontmatter block followed by the `Tools` class.

### Frontmatter Fields

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

Only `id` is required. The loader installs any `requirements` before executing
the file ([PLUGIN_GUIDE.md](../external/PLUGIN_GUIDE.md#L5-L29)). Other common
fields are:

- `title` – human friendly name shown in WebUI
- `author` / `author_url` – attribution displayed in the library
- `git_url` – optional repository link
- `description` – short explanation for the LLM and users
- `required_open_webui_version` – minimum WebUI version
- `requirements` – Python packages installed before loading
- `version` – your tool version string
- `licence` – licence identifier

### Writing Tool Methods

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

The method name becomes the function name. Parameter names and `:param` blocks
populate the tool schema. Type hints are mandatory so the loader can build the
JSON schema for function calling. Nested hints such as `list[tuple[str, int]]`
are supported.

### Valves and UserValves

`Valves` define global settings while `UserValves` allow per-user overrides. Values are hydrated from the database before each call ([FILTER_GUIDE.md](../external/FILTER_GUIDE.md#L120-L145)).

## Using Tools in WebUI

### Enabling Tools

Tools can be enabled per chat or per model. Click the ➕ icon in the chat input to toggle individual tools or enable them by default under **Workspace ▸ Models**. The optional **AutoTool Filter** helps choose the right tool when multiple are available.

### Default vs Native Function Calling

Tools work with any model using a prompt based helper, but models with built in function calling can chain tools natively. When native mode is disabled the pipe warns the user:

```python
if __tools__ and __metadata__.get("function_calling") != "native":
    await __event_emitter__({
        "type": "chat:completion",
        "data": {
            "content": (
                "🛑 Tools detected, but native function calling is disabled.\n\n"
                "To enable tools in this chat, switch Function Calling to 'Native'."
            ),
        },
    })
```

Switch modes from **Chat Controls ▸ Advanced Params**.

### Uploading with Frontmatter

When a file is uploaded the loader applies `replace_imports`, installs `requirements` and writes the code to a temporary file before executing it ([PLUGIN_GUIDE.md](../external/PLUGIN_GUIDE.md#L33-L59)). Use `.scripts/publish_to_webui.py` to upload a tool via the API.

## Calling Tools from a Pipe

```python
async def pipe(self, body, __tools__):
    add = __tools__["add"]["callable"]
    result = await add(a=1, b=2)
    return str(result)
```

Remote tool servers are also supported. When a tool id starts with `server:` the loader fetches an OpenAPI document, converts each operation into a tool definition and proxies calls via [`execute_tool_server`](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/tools.py#L38-L71) ([TOOLS_GUIDE.md](../external/TOOLS_GUIDE.md#L53-L103)).

## Internals

### Tool Discovery

`backend/open_webui/utils/tools.py` converts methods into async callables and JSON specs. `get_tools` loads modules by id and prepares the mapping ready for the chat pipeline【F:external/open-webui/backend/open_webui/utils/tools.py†L68-L206】.

### Parameter Injection

`convert_function_to_pydantic_model` turns type hints and docstrings into Pydantic models at lines 264–303【F:external/open-webui/backend/open_webui/utils/tools.py†L264-L303】. Parameters such as `__event_emitter__`, `__user__` and `__metadata__` are injected only when requested, mirroring the behaviour for pipes (see [functions/pipes/README.md](../functions/pipes/README.md#parameter-injection)).

### Remote Tool Servers

Connections to external tool servers are listed in `TOOL_SERVER_CONNECTIONS`. The router caches the OpenAPI specs on first access【F:external/open-webui/backend/open_webui/routers/tools.py†L38-L71】 before merging them with local tools.

### Events and Callbacks

Tool methods can emit live updates using `__event_emitter__` or prompt the user via `__event_call__`:

```python
async def example_tool(__event_emitter__, __event_call__):
    await __event_emitter__({"type": "status", "data": {"description": "Loading", "done": False}})
    ok = await __event_call__({"type": "confirmation", "data": {"title": "Continue?", "message": "Run step?"}})
    if ok:
        await __event_emitter__({"type": "replace", "data": {"content": "step complete"}})
```

`__event_call__` can also run JavaScript (`execute`) or request text (`input`). The emitter supports `message`, `replace`, `status`, `citation` and `notification` event types.

## Further Reading

- [TOOLS_GUIDE.md](../external/TOOLS_GUIDE.md)
- [PLUGIN_GUIDE.md](../external/PLUGIN_GUIDE.md)

## TODO

### Research Topics
- Document how tools are stored in the database via `ToolsTable`.
- Investigate how valves are cached and refreshed.

### Example Ideas
- Provide a full remote tool server example.
- Explain troubleshooting steps for import errors.

### Documentation Placeholders
- TODO: describe how to bundle multiple tools in one file.
- TODO: show best practices for unit testing tools.

### Field Reference TODO
- TODO: compile a table of all frontmatter fields and their meanings.
