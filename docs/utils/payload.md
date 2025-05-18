# payload.py

`backend/open_webui/utils/payload.py` defines a set of small helpers that massage
chat payloads before they are sent to an upstream model.

These routines operate on the request body in place. They convert parameter
types, inject system prompts and translate OpenAI style payloads to
Ollama's format.  The goal is to accept flexible input from Open WebUI's HTTP
API while keeping the model specific schemas consistent.

## System prompt injection

`apply_model_system_prompt_to_body` inserts a system message at the beginning of
the conversation. It handles the legacy `user` template variables as well as the
new metadata driven placeholders.

```python
form_data = {"messages": [{"role": "user", "content": "Hello"}]}
params = {"system": "Hello {user_name}"}
metadata = {"variables": {"user_name": "Alice"}}
apply_model_system_prompt_to_body(params, form_data, metadata)
# form_data['messages'][0] becomes the injected system message
```

The function uses `prompt_template` from `task.py` and
`add_or_update_system_message` from `misc.py` to perform the merge.

## Parameter normalization

Models expose slightly different parameter names.  Two helpers convert common
OpenAI fields to the appropriate types and names:

- `apply_model_params_to_body_openai`
- `apply_model_params_to_body_ollama`

They iterate over a mapping of expected keys and cast functions.  For example:

```python
form = {}
params = {"temperature": "0.7", "max_tokens": "128"}
apply_model_params_to_body_openai(params, form)
# form == {"temperature": 0.7, "max_tokens": 128}
```

The Ollama variant additionally renames `max_tokens` to `num_predict` and moves
`keep_alive` and `format` from the `options` section if present.

## Converting message formats

Ollama expects a slightly different message structure than OpenAI.  The
`convert_messages_openai_to_ollama` helper walks through each chat entry and
splits text, images and tool calls into the layout expected by Ollama's API.

```python
messages = [
    {"role": "user", "content": [
        {"type": "text", "text": "Hi"},
        {"type": "image_url", "image_url": {"url": "img.png"}}
    ]},
]
convert_messages_openai_to_ollama(messages)
```

`convert_payload_openai_to_ollama` wraps this function and copies the remaining
fields (`model`, `stream`, etc.) producing a final dictionary that can be posted
to `/api/chat` on an Ollama server.

