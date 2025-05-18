# plugin.py

`backend/open_webui/utils/plugin.py` is responsible for loading and executing extension modules.  Tools, pipe functions and filters are stored as source code in the database and this loader turns that code into live Python objects.

## Frontmatter blocks

A plugin file can begin with a triple quoted **frontmatter** block declaring metadata.  The loader parses it with `extract_frontmatter`.

```python
"""
requirements: requests, pydantic
other_field: demo
"""
```

Lines 18‑51 implement the parser which scans until the closing quotes and stores key/value pairs in a dictionary.

## Import rewriting

Extensions often import helpers using short paths like `from utils.chat import ...`.  `replace_imports` rewrites these statements so they reference the actual `open_webui` package:

```python
replacements = {
    "from utils": "from open_webui.utils",
    "from apps": "from open_webui.apps",
    "from main": "from open_webui.main",
    "from config": "from open_webui.config",
}
```

## Module creation

`load_tool_module_by_id` and `load_function_module_by_id` both follow the same flow:

1. Fetch the source code from the database when `content` is not provided.
2. Apply `replace_imports` and update the stored record.
3. Extract frontmatter and call `install_frontmatter_requirements` if a `requirements` field is present.
4. Create a `types.ModuleType` instance and execute the code inside it using `exec`.
5. Instantiate the class that matches the extension type.

The temporary file created around lines 91‑99 sets `__file__` so relative paths behave correctly when executed.

### Selecting the class

After executing the module, the loader returns the first matching class:

```python
if hasattr(module, "Pipe"):
    return module.Pipe(), "pipe", frontmatter
elif hasattr(module, "Filter"):
    return module.Filter(), "filter", frontmatter
elif hasattr(module, "Action"):
    return module.Action(), "action", frontmatter
```

## Installing dependencies

`install_frontmatter_requirements` is a thin wrapper around `pip`.  It receives a comma separated string and invokes:

```python
subprocess.check_call(
    [sys.executable, "-m", "pip", "install"]
    + PIP_OPTIONS
    + req_list
    + PIP_PACKAGE_INDEX_OPTIONS,
)
```

`install_tool_and_function_dependencies` iterates over all stored tools and active functions, collects their `requirements` frontmatter and installs them in one go.
