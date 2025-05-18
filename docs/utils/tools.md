# tools.py

`backend/open_webui/utils/tools.py` discovers tool functions by id and prepares them for execution.

It handles:
- Loading tool modules via `plugin.load_tool_module_by_id`.
- Converting Python callables or tool server endpoints into async functions.
- Parsing type hints and docstrings with `convert_function_to_pydantic_model`.
- Building OpenAI style JSON specs from Pydantic models.
- Integrating with **OpenAPI tool servers** for remote actions.

## Tool server integration

Tool servers expose functions over HTTP by serving an OpenAPI document. The
utilities below download the spec, convert each operation into a ChatGPT style
tool payload and later proxy the call:

```python
from open_webui.utils.tools import (
    get_tool_servers_data,
    execute_tool_server,
)

servers = [
    {"url": "https://example.com/api", "config": {"enable": True}},
]

tool_servers = await get_tool_servers_data(servers)
spec = tool_servers[0]["specs"][0]  # first operation as a tool payload

result = await execute_tool_server(
    token="",
    url=tool_servers[0]["url"],
    name=spec["name"],
    params={"foo": "bar"},
    server_data=tool_servers[0],
)
```

`convert_openapi_to_tool_payload` translates each `operationId` to the JSON
structure expected by the OpenAI API. The snippet below shows the core loop
around lines 365–438 where parameters are collected and request bodies are
flattened into a single schema:

```python
for path, methods in openapi_spec.get("paths", {}).items():
    for method, operation in methods.items():
        if operation.get("operationId"):
            tool = {
                "type": "function",
                "name": operation.get("operationId"),
                "description": operation.get(
                    "description",
                    operation.get("summary", "No description available."),
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            }
            # path and query parameters are mapped to the tool schema
```

These lines continue by resolving request body schemas and appending the final
tool object to the list returned by the function.
