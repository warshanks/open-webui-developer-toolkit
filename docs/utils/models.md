# models.py

`backend/open_webui/utils/models.py` compiles the list of chat models that users
can pick from.  It queries remote providers like OpenAI and Ollama, discovers
locally installed function based **pipes** and finally merges custom entries from
the database.  The resulting structure is stored on
`request.app.state.MODELS` for quick access by the HTTP routes.

## Function reference

### `get_all_base_models`

Collects built‑in models from all configured sources:

- `openai.get_all_models` and `ollama.get_all_models` are called when their
  respective APIs are enabled.  Ollama models are normalised into OpenAI's format
  as shown below.
- `get_function_models(request)` returns custom pipe definitions so they appear
  alongside normal models.

```python
if request.app.state.config.ENABLE_OPENAI_API:
    openai_models = await openai.get_all_models(request, user=user)
    openai_models = openai_models["data"]

if request.app.state.config.ENABLE_OLLAMA_API:
    ollama_models = await ollama.get_all_models(request, user=user)
    ollama_models = [
        {
            "id": model["model"],
            "name": model["name"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": "ollama",
            "ollama": model,
            "tags": model.get("tags", []),
        }
        for model in ollama_models["models"]
    ]

function_models = await get_function_models(request)
models = function_models + openai_models + ollama_models
```

### `get_all_models`

Builds the full list that the UI consumes.  After obtaining the base models it
adds optional **evaluation arena** items and merges any user defined presets
stored in the `Models` table.  Actions declared in the model metadata are
resolved by loading the corresponding modules:

```python
for model in models:
    action_ids = [
        action_id
        for action_id in list(set(model.pop("action_ids", []) + global_action_ids))
        if action_id in enabled_action_ids
    ]

    model["actions"] = []
    for action_id in action_ids:
        action_function = Functions.get_function_by_id(action_id)
        if action_function is None:
            raise Exception(f"Action not found: {action_id}")

        function_module = get_function_module_by_id(action_id)
        model["actions"].extend(
            get_action_items_from_module(action_function, function_module)
        )
```

Custom presets inherit the `owned_by` and optional `pipe` from their base model
and may expose additional actions via their metadata.  When finished the
function writes the dictionary to `request.app.state.MODELS` and returns the
list.

### `check_model_access`

Validates that a user can see the given model.  Arena models honour the
`access_control` rules stored in their metadata.  For regular models the
function consults `Models.get_model_by_id` and verifies ownership or explicit
permissions via `has_access`.

