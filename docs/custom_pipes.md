# Custom Pipes

Open WebUI allows administrators to register Python functions as chat models. These **pipes** are loaded dynamically by `backend/open_webui/utils/plugin.py` and executed by `backend/open_webui/functions.py`.

## Loading a pipe

`load_function_module_by_id` reads the source code from the database, rewrites short imports and executes the module inside a temporary namespace. When the module exposes a `class Pipe` instance it is returned to the caller:

```python
if hasattr(module, "Pipe"):
    return module.Pipe(), "pipe", frontmatter
```

Any triple quoted frontmatter block at the start of the file is parsed with `extract_frontmatter` so dependencies can be installed automatically.

### Frontmatter fields

The optional frontmatter block may contain arbitrary key/value pairs. The most
common field is `requirements` which lists Python packages that should be
installed before the module runs:

```python
"""
requirements: httpx, numpy
other_field: example
"""
```

`plugin.py` installs these packages using `pip` and returns the metadata along
with the pipe object. Other fields can be read inside the module if desired.


### Loader internals

The loader lives in `backend/open_webui/utils/plugin.py` and performs a few important steps:

1. Retrieve the stored code and run `replace_imports` to convert short paths like `from utils.chat import ...` into absolute `open_webui` imports.
2. Parse any frontmatter and call `install_frontmatter_requirements` so dependencies are installed before execution.
3. Create a temporary file to populate `__file__` and execute the source inside a new module object.
4. Return the first matching class exported by the file.

The core of `load_function_module_by_id` is shown below:

```python
    def load_function_module_by_id(function_id, content=None):
        if content is None:
            function = Functions.get_function_by_id(function_id)
            if not function:
                raise Exception(f"Function not found: {function_id}")
            content = function.content
    
            content = replace_imports(content)
            Functions.update_function_by_id(function_id, {"content": content})
        else:
            frontmatter = extract_frontmatter(content)
            install_frontmatter_requirements(frontmatter.get("requirements", ""))
    
        module_name = f"function_{function_id}"
        module = types.ModuleType(module_name)
        sys.modules[module_name] = module
    
        # Create a temporary file and use it to define `__file__` so
        # that it works as expected from the module's perspective.
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        try:
            with open(temp_file.name, "w", encoding="utf-8") as f:
                f.write(content)
            module.__dict__["__file__"] = temp_file.name
    
            # Execute the modified content in the created module's namespace
            exec(content, module.__dict__)
            frontmatter = extract_frontmatter(content)
            log.info(f"Loaded module: {module.__name__}")
    
            # Create appropriate object based on available class type in the module
            if hasattr(module, "Pipe"):
                return module.Pipe(), "pipe", frontmatter
            elif hasattr(module, "Filter"):
                return module.Filter(), "filter", frontmatter
            elif hasattr(module, "Action"):
                return module.Action(), "action", frontmatter
            else:
                raise Exception("No Function class found in the module")
        except Exception as e:
            log.error(f"Error loading module: {function_id}: {e}")
            # Cleanup by removing the module in case of error
            del sys.modules[module_name]
    
            Functions.update_function_by_id(function_id, {"is_active": False})
            raise e
        finally:
            os.unlink(temp_file.name)
```


On startup the helper `install_tool_and_function_dependencies` scans every stored extension and installs their requirements in bulk:

```python
    def install_tool_and_function_dependencies():
        """
        Install all dependencies for all admin tools and active functions.
    
        By first collecting all dependencies from the frontmatter of each tool and function,
        and then installing them using pip. Duplicates or similar version specifications are
        handled by pip as much as possible.
        """
        function_list = Functions.get_functions(active_only=True)
        tool_list = Tools.get_tools()
    
        all_dependencies = ""
        try:
            for function in function_list:
                frontmatter = extract_frontmatter(replace_imports(function.content))
                if dependencies := frontmatter.get("requirements"):
                    all_dependencies += f"{dependencies}, "
            for tool in tool_list:
                # Only install requirements for admin tools
                if tool.user.role == "admin":
                    frontmatter = extract_frontmatter(replace_imports(tool.content))
                    if dependencies := frontmatter.get("requirements"):
                        all_dependencies += f"{dependencies}, "
    
            install_frontmatter_requirements(all_dependencies.strip(", "))
        except Exception as e:
            log.error(f"Error installing requirements: {e}")
```
## Execution flow

`generate_function_chat_completion` retrieves the pipe and prepares extra parameters such as the current user, associated files and websocket callbacks. These values are only passed if the pipe declares matching arguments:

```python
extra_params = {
    "__event_emitter__": __event_emitter__,
    "__event_call__": __event_call__,
    "__chat_id__": metadata.get("chat_id", None),
    "__session_id__": metadata.get("session_id", None),
    "__message_id__": metadata.get("message_id", None),
    "__task__": __task__,
    "__task_body__": __task_body__,
    "__files__": files,
    "__user__": {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    },
    "__metadata__": metadata,
    "__request__": request,
}
```

### Event hooks

`__event_emitter__` and `__event_call__` allow a pipe to send websocket events
to the client.  They wrap the same helpers used by the server middleware so
messages appear in the UI immediately:

```python
async def pipe(self, body, __event_emitter__):
    await __event_emitter__({"type": "log", "data": "working"})
    return "done"
```

### Streaming responses

When `form_data["stream"]` is true the return value may be a generator,
`StreamingResponse` or async generator.  Each yielded item is wrapped in the
OpenAI streaming chunk format and forwarded to the browser:

```python
class Pipe:
    def pipe(self, body):
        for word in body["messages"][-1]["content"].split():
            yield word
```

Non streaming calls simply return the concatenated string result.

If `form_data["stream"]` is truthy the function yields chunks produced by the pipe using `StreamingResponse`. Otherwise it waits for the result and converts it to the OpenAI completion format.

## Creating a pipe

A minimal pipe looks like this:

```python
"""
requirements: requests
"""

class Pipe:
    async def pipe(self, body, __user__, __event_emitter__):
        msg = body["messages"][-1]["content"]
        await __event_emitter__({"type": "log", "data": msg})
        return f"echo: {msg}"
```

Upload the file through the Functions UI and enable it. The `requirements` field ensures `requests` is installed before the module runs.

### Manifold pipes

When a module defines a `pipes` attribute it can act as a **manifold** exposing several models. The attribute can be a list or a function returning a list:

```python
class Pipe:
    name = "translator: "
    pipes = [
        {"id": "en", "name": "English"},
        {"id": "es", "name": "Spanish"},
    ]

    def pipe(self, body, __metadata__):
        lang = __metadata__["model"].split(".")[-1]
        text = body["messages"][-1]["content"]
        return f"[{lang}] {text}"
```

`get_function_models` expands these entries so users can select `pipe_id.sub_id` as a normal model id.

Pipes integrate with filters and tools just like built‑in models, making them a powerful extension mechanism.

## Valve configuration

Pipes may define a `Valves` class to describe adjustable settings. When present
the server stores these values and hydrates `function_module.valves` before each
execution.  A complementary `UserValves` model provides per‑user overrides via
`__user__["valves"]`.

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

The functions router exposes `/id/{id}/valves` and `/id/{id}/valves/user` so
administrators can update these values without re-uploading the code.

## Invoking tools from a pipe

When a chat request specifies tool IDs they are resolved to callables and passed
via the `__tools__` dictionary. A pipe can run them directly:

```python
class Pipe:
    async def pipe(self, body, __tools__):
        add = __tools__["add"]["callable"]
        result = await add(a=1, b=2)
        return str(result)
```

`get_tools` in `utils.tools` handles the conversion and provides each function's
OpenAI-style spec under `spec`.

### Pipe lifecycle

Custom pipes are only loaded once per server process. `get_function_module_by_id` checks `request.app.state.FUNCTIONS` and calls `load_function_module_by_id` when necessary:

```python
if pipe_id not in request.app.state.FUNCTIONS:
    function_module, _, _ = load_function_module_by_id(pipe_id)
    request.app.state.FUNCTIONS[pipe_id] = function_module
else:
    function_module = request.app.state.FUNCTIONS[pipe_id]

if hasattr(function_module, "valves") and hasattr(function_module, "Valves"):
    valves = Functions.get_function_valves_by_id(pipe_id)
    function_module.valves = function_module.Valves(**(valves or {}))
```

The module object exposes the `pipe` method, any valve classes and optional `pipes` metadata. `generate_function_chat_completion` uses this information to build the execution parameters, install tools and forward WebSocket callbacks. Each call hydrates the valve values before invoking the handler:

```python
pipe = function_module.pipe
params = get_function_params(function_module, form_data, user, extra_params)
res = await execute_pipe(pipe, params)
```

This lifecycle keeps startup fast while ensuring configuration changes take effect the next time a pipe is triggered.
