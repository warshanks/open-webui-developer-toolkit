# Custom Pipes

Open WebUI allows administrators to register Python functions as chat models. These **pipes** are loaded dynamically by `backend/open_webui/utils/plugin.py` and executed by `backend/open_webui/functions.py`.

The `load_function_module_by_id` helper returns a `Pipe` object when the uploaded module defines a `class Pipe`. The relevant logic lives around lines 150‑156:

```python
if hasattr(module, "Pipe"):
    return module.Pipe(), "pipe", frontmatter
```

During chat completion `generate_function_chat_completion` calls the pipe and streams or returns its output. Parameters such as files, user info and event emitters are assembled before invocation:

```python
extra_params = {
    "__event_emitter__": __event_emitter__,
    "__event_call__": __event_call__,
    "__chat_id__": metadata.get("chat_id", None),
    "__session_id__": metadata.get("session_id", None),
    "__message_id__": metadata.get("message_id", None),
    ...
}
```

This mechanism lets extensions act as fully fledged models that integrate with filters, tools and the rest of the middleware pipeline.
