# plugin.py

`backend/open_webui/utils/plugin.py` dynamically loads extension code for tools, filters and **pipes**.

Key duties:
- Replace imports so user supplied modules reference `open_webui` internals.
- Install Python package requirements defined in a frontmatter block.
- Execute the module and return the object matching the available class (`Pipe`, `Filter` or `Action`).

The `load_function_module_by_id` helper is called when a custom pipe is invoked. Lines below show the branching logic that creates the right object:

```python
if hasattr(module, "Pipe"):
    return module.Pipe(), "pipe", frontmatter
elif hasattr(module, "Filter"):
    return module.Filter(), "filter", frontmatter
elif hasattr(module, "Action"):
    return module.Action(), "action", frontmatter
```

These objects are cached per `function_id` so later calls skip re-importing the module.
