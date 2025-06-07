# File Handler Reference

Open WebUI reads uploaded files and injects their contents into the system prompt. Extensions can skip this behavior when they manage files themselves.

Declare a module level variable `file_handler = True` to signal that a filter's `inlet` or tool handles file uploads. The manifold.py checks this flag and removes the files from the payload after your handler runs:

```python
# Check if the function has a file_handler variable
if filter_type == "inlet" and hasattr(function_module, "file_handler"):
    skip_files = function_module.file_handler
...
if skip_files and "files" in form_data.get("metadata", {}):
    del form_data["files"]
    del form_data["metadata"]["files"]
```

## Filters

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

Example:

```python
# image_tagging_tool.py

class Tools:
    def __init__(self):
        self.file_handler = True  # prevent default file injection
        self.citation = False  # disable auto citations (optional)
        self.valves = self.Valves()

```

## Pipes

Pipes do not support a `file_handler` flag. If it's not disabled via any of the enabled tools or filters, you will see the the file contents injected in the system prompt.
