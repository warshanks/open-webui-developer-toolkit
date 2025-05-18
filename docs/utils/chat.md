# chat.py

`backend/open_webui/utils/chat.py` coordinates chat completions across multiple
sources.

It acts as the main entry point for the middleware once the request payload has
been normalised.  The helpers in this file decide **which backend** to invoke
and stream results back to the client.

Key points:
* Chooses between OpenAI, Ollama or a custom pipe based on the selected model.
* Applies inlet/outlet filters through `routers.pipelines` when configured.
* Exposes `generate_direct_chat_completion`, `generate_chat_completion`,
  `chat_completed` and `chat_action` used by the HTTP routes.

The rest of this document focuses on `generate_chat_completion` which performs
the main routing logic.

## `generate_chat_completion`

This asynchronous function receives the processed form data and determines how
the chat should be executed.  When the request originated from a "direct"
connection (typically from another WebUI instance) it forwards the payload over
the websocket channel.  Otherwise it performs a number of checks and invokes the
appropriate backend.

Pseudo-code outline:

```
if request.state.direct:
    return generate_direct_chat_completion(...)

if not bypass_filter and user.role == "user":
    check_model_access(user, model)

if model.owned_by == "arena":
    # pick a random model and re-enter generate_chat_completion
    ...
elif model.pipe:
    return generate_function_chat_completion(...)
elif model.owned_by == "ollama":
    convert_payload_openai_to_ollama()
    return generate_ollama_chat_completion(...)
else:
    return generate_openai_chat_completion(...)
```

### Streaming direct completions

When a direct connection is used with `stream=True` the function registers a
socket listener and yields chunks as they arrive.  The relevant section is shown
below (lines 81‑136 in the upstream file):

```python
q = asyncio.Queue()

async def message_listener(sid, data):
    await q.put(data)

sio.on(channel, message_listener)

res = await event_caller({
    "type": "request:chat:completion",
    "data": {
        "form_data": form_data,
        "model": models[form_data["model"]],
        "channel": channel,
        "session_id": session_id,
    },
})

if res.get("status", False):
    async def event_generator():
        while True:
            data = await q.get()
            if isinstance(data, dict) and data.get("done"):
                break
            yield f"data: {json.dumps(data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Arena model selection

Models owned by `"arena"` act as wrappers that randomly choose another model at
runtime.  After selecting the model id the function re-invokes itself so the
normal logic applies.  A simplified excerpt (lines 203‑249) illustrates the
approach:

```python
model_ids = model.get("info", {}).get("meta", {}).get("model_ids")
if model_ids and filter_mode == "exclude":
    model_ids = [m["id"] for m in request.app.state.MODELS.values()
                 if m.get("owned_by") != "arena" and m["id"] not in model_ids]

selected_model_id = random.choice(model_ids)
form_data["model"] = selected_model_id

if form_data.get("stream"):
    async def stream_wrapper(stream):
        yield f"data: {json.dumps({'selected_model_id': selected_model_id})}\n\n"
        async for chunk in stream:
            yield chunk
    response = await generate_chat_completion(request, form_data, user, bypass_filter=True)
    return StreamingResponse(stream_wrapper(response.body_iterator), media_type="text/event-stream")
else:
    result = await generate_chat_completion(request, form_data, user, bypass_filter=True)
    return {**result, "selected_model_id": selected_model_id}
```

### Outlet filters

After a model has produced a response `chat_completed` is called.  It gathers the
configured filter functions for the model and executes them via
`process_filter_functions`:

```python
filter_functions = [Functions.get_function_by_id(fid)
                    for fid in get_sorted_filter_ids(model)]
result, _ = await process_filter_functions(
    request=request,
    filter_functions=filter_functions,
    filter_type="outlet",
    form_data=data,
    extra_params=extra_params,
)
```

This mechanism lets extensions modify the final message before it is emitted to
the client.
