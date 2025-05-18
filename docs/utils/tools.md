# tools.py

`backend/open_webui/utils/tools.py` discovers tool functions by id and prepares them for execution.

It handles:
- Loading tool modules via `plugin.load_tool_module_by_id`.
- Converting Python callables or tool server endpoints into async functions.
- Building OpenAI style JSON specs from Pydantic models.
