# filter.py

`backend/open_webui/utils/filter.py` runs extra processing functions before and after a chat request.

Functions exported:
- `get_sorted_filter_ids(model)` computes a priority ordered list of filter function IDs.
- `process_filter_functions(request, filter_functions, filter_type, form_data, extra_params)` loads each function via `plugin.load_function_module_by_id` and calls its `inlet`, `outlet` or `stream` method.

These hooks allow extensions to modify the chat payload or streaming chunks.
