# File Handler Reference

Open WebUI reads uploaded files and injects their contents into the system prompt. Extensions can skip this behavior when they manage files themselves.

## Filters

Declare a module level variable `file_handler = True` to signal that a filter's `inlet` handles file uploads. The filter loader checks this flag and removes the files from the payload after your handler runs:

```python
# Check if the function has a file_handler variable
if filter_type == "inlet" and hasattr(function_module, "file_handler"):
    skip_files = function_module.file_handler
...
if skip_files and "files" in form_data.get("metadata", {}):
    del form_data["files"]
    del form_data["metadata"]["files"]
```

Example:

```python
class Filter:
    def __init__(self) -> None:
        # Let the loader know we will process uploaded files ourselves
        self.file_handler = True  # disable built-in file injection
        self.citation = False  # optional, manage citations yourself
        self.valves = self.Valves()

    async def inlet(self, body: dict) -> dict:
        # Uploaded files are available under body["files"]
        return body
```

## Tools

When a tool handles uploaded files, define `file_handler = True` either at module scope or on the `Tools` class. The loader exposes this flag through metadata so the middleware skips injecting file contents:

```python
"metadata": {
    "file_handler": hasattr(module, "file_handler") and module.file_handler,
    "citation": hasattr(module, "citation") and module.citation,
}
...
if tools[tool_function_name].get("metadata", {}).get("file_handler", False):
    skip_files = True
```

Example:

```python
# image_tagging_tool.py

class Tools:
    def __init__(self):
        self.file_handler = True  # prevent default file injection
        self.citation = False  # disable auto citations (optional)
        self.valves = self.Valves()

    async def run(self, files: list[str], query: str = ""):
        # inspect or modify `files` here before returning
        return {"tags": ["example"]}
```

## Pipes

Pipes do not support a `file_handler` flag. They may remove the `files` entry from the payload to prevent the default file handler from running.
