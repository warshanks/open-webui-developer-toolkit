# Tools Guide

## Overview
Tools extend Open WebUI with Python functions for tasks like web search or image generation. Each file defines a `Tools` class whose methods become callable tools. The loader executes the file via `plugin.load_tool_module_by_id` which rewrites short imports, installs any packages and exposes the methods as OpenAI function specs.

Typical capabilities include:

- **Web search** for real-time answers
- **Image generation** from text prompts
- **Voice output** using text-to-speech services

This folder complements the [pipes](../functions/pipes/README.md) and [filters](../functions/filters/README.md) guides. Tools provide standalone actions that pipes can invoke during a chat request.

## Installing Tools
You can install tools from the **Community Tool Library** or by uploading a Python file directly. Click *Get* in the library, enter your WebUI address and use “Import to WebUI”.

**Safety tip:** Only import tools from sources you trust as they execute Python code on your server.

## Anatomy of a Tool
A toolkit lives in a single Python file. Each file begins with a frontmatter block followed by a `Tools` class.

### Frontmatter metadata
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
Only `id` is required but the extra fields make maintenance easier. The loader parses this header and installs any `requirements` before executing the file【F:external/PLUGIN_GUIDE.md†L5-L29】.

### Tools class and methods
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

## Using Tools in WebUI
Tools can be enabled per chat or per model. Click the ➕ icon in the chat input to toggle individual tools or enable them by default under **Workspace ▸ Models**. The optional **AutoTool Filter** helps choose the right tool when multiple are available.

### Default vs native function calling
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

### Uploading with frontmatter
When a file is uploaded the loader applies `replace_imports`, installs `requirements` and writes the code to a temporary file before executing it【F:external/PLUGIN_GUIDE.md†L33-L59】. Use `.scripts/publish_to_webui.py` to upload a tool via the API.

## Internals
### Tool discovery
`backend/open_webui/utils/tools.py` turns each method into an async callable and a JSON spec. `convert_function_to_pydantic_model` parses the signature and docstring while `convert_pydantic_model_to_openai_function_spec` produces the final format【F:external/open-webui/backend/open_webui/utils/tools.py†L49-L65】【F:external/TOOLS_GUIDE.md†L3-L10】. `get_tools()` assembles the mapping ready for the chat pipeline【F:external/TOOLS_GUIDE.md†L12-L28】.

### Parameter injection
`get_tools()` only passes parameters requested in the signature. Useful names mirror those available to pipes and filters such as `__event_emitter__`, `__user__` and `__metadata__`【F:functions/pipes/README.md†L66-L78】.

### Calling tools from a pipe
```python
async def pipe(self, body, __tools__):
    add = __tools__["add"]["callable"]
    result = await add(a=1, b=2)
    return str(result)
```
Remote tool servers are also supported. When a tool id starts with `server:` the loader fetches an OpenAPI document, converts each operation into a tool definition and proxies calls via `execute_tool_server`【F:external/open-webui/backend/open_webui/routers/tools.py†L38-L71】【F:external/TOOLS_GUIDE.md†L53-L103】.

### Events and callbacks
Tool methods can emit live updates using `__event_emitter__` or prompt the user via `__event_call__`:
```python
async def example_tool(__event_emitter__, __event_call__):
    await __event_emitter__({"type": "status", "data": {"description": "Loading", "done": False}})
    ok = await __event_call__({"type": "confirmation", "data": {"title": "Continue?", "message": "Run step?"}})
    if ok:
        await __event_emitter__({"type": "replace", "data": {"content": "step complete"}})
```
`__event_call__` can also run JavaScript (`execute`) or request text (`input`). The emitter supports `message`, `replace`, `status`, `citation` and `notification` event types.

## TODO
- Document how tools are stored in the database via `ToolsTable`.
- Add a security best practices section for third-party tools.
- Provide a full remote tool server example.
- Explain troubleshooting steps for import errors.
