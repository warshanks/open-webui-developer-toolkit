# filter.py

`backend/open_webui/utils/filter.py` exposes a lightweight plugin system for intercepting chat requests. Filters can mutate the request body before the model runs (`inlet`), transform the final message (`outlet`) or handle each streaming event (`stream`).

## Prioritizing filters

`get_sorted_filter_ids(model)` merges globally active filters with the ids listed under a model's metadata. Only enabled filters are returned and the list is sorted by the `priority` value stored in each filter's valves object:

```python
def get_sorted_filter_ids(model: dict):
    def get_priority(function_id):
        function = Functions.get_function_by_id(function_id)
        if function is not None:
            valves = Functions.get_function_valves_by_id(function_id)
            return valves.get("priority", 0) if valves else 0
        return 0

    filter_ids = [function.id for function in Functions.get_global_filter_functions()]
    if "info" in model and "meta" in model["info"]:
        filter_ids.extend(model["info"]["meta"].get("filterIds", []))
        filter_ids = list(set(filter_ids))

    enabled_filter_ids = [
        function.id
        for function in Functions.get_functions_by_type("filter", active_only=True)
    ]

    filter_ids = [fid for fid in filter_ids if fid in enabled_filter_ids]
    filter_ids.sort(key=get_priority)
    return filter_ids
```

Filters with higher priority numbers run later in the chain.

## Running filter code

`process_filter_functions(request, filter_functions, filter_type, form_data, extra_params)` loads each filter module and executes the appropriate handler. File cleanup, valve hydration and argument selection all happen transparently:

```python
        # Prepare handler function
        handler = getattr(function_module, filter_type, None)
        if not handler:
            continue

        # Check if the function has a file_handler variable
        if filter_type == "inlet" and hasattr(function_module, "file_handler"):
            skip_files = function_module.file_handler

        # Apply valves to the function
        if hasattr(function_module, "valves") and hasattr(function_module, "Valves"):
            valves = Functions.get_function_valves_by_id(filter_id)
            function_module.valves = function_module.Valves(
                **(valves if valves else {})
            )

        try:
            # Prepare parameters
            sig = inspect.signature(handler)

            params = {"body": form_data}
            if filter_type == "stream":
                params = {"event": form_data}

            params = params | {
                k: v
                for k, v in {
                    **extra_params,
                    "__id__": filter_id,
                }.items()
                if k in sig.parameters
            }

            # Handle user parameters
            if "__user__" in sig.parameters:
                if hasattr(function_module, "UserValves"):
                    try:
                        params["__user__"]["valves"] = function_module.UserValves(
                            **Functions.get_user_valves_by_id_and_user_id(
                                filter_id, params["__user__"]["id"]
                            )
                        )
                    except Exception as e:
                        log.exception(f"Failed to get user values: {e}")

            # Execute handler
            if inspect.iscoroutinefunction(handler):
                form_data = await handler(**params)
            else:
                form_data = handler(**params)

        except Exception as e:
            log.debug(f"Error in {filter_type} handler {filter_id}: {e}")
            raise e

    # Handle file cleanup for inlet
    if skip_files and "files" in form_data.get("metadata", {}):
        del form_data["files"]
        del form_data["metadata"]["files"]

    return form_data, {}
```

Handlers may be synchronous or async and can declare optional parameters like `__user__` to access user specific valve values.

## Example

A minimal filter that appends the current timestamp to the latest message:

```python
# custom_timestamp_filter.py
from datetime import datetime

def outlet(body, __id__):
    body["messages"][-1]["content"] += f" ({datetime.utcnow().isoformat()} UTC)"
    return body
```

Upload the file via the Functions UI, mark it as a filter and enable it. `process_filter_functions` imports the module and invokes `outlet` before sending the response back to the client.
