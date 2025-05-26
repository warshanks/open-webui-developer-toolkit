# Events: `__event_emitter__` and `__event_call__`

Open WebUI extensions can push real-time updates to the UI. Each Tool or Pipe
receives two async helpers:

* `__event_emitter__` – fire-and-forget events
* `__event_call__` – events that wait for user input and return the user's
  response

Both helpers expect a dictionary `{"type": str, "data": dict}`.

`get_event_emitter()` gathers every active session for the calling user (plus the
current request's session when available) and emits the payload to each one:

```python
session_ids = list(
    set(
        USER_POOL.get(user_id, [])
        + ([request_info.get("session_id")] if request_info.get("session_id") else [])
    )
)
```
【F:external/open-webui/backend/open_webui/socket/main.py†L305-L317】

The returned helper is an asynchronous function that uses Python Socket.IO to
broadcast the given payload to each collected session.

`get_event_call()` returns another helper bound to the current request's session.
It uses [`sio.call`](https://python-socketio.readthedocs.io/en/latest/api.html#socketio.AsyncServer.call)
to send the payload only to that session and waits for the browser to respond:

```python
async def __event_caller__(event_data):
    response = await sio.call(
        "chat-events",
        {
            "chat_id": request_info.get("chat_id", None),
            "message_id": request_info.get("message_id", None),
            "data": event_data,
        },
        to=request_info["session_id"],
    )
    return response
```
【F:external/open-webui/backend/open_webui/socket/main.py†L374-L386】

The returned value is whatever the frontend callback supplies—typically a
boolean for `confirmation` events or a string for `input` prompts. Unlike the
emitter, this helper does not alter the database automatically.

## Database persistence

The helper produced by `get_event_emitter` in `socket/main.py` first collects the
user's active session IDs from `USER_POOL`. With `update_db=True` (the default)
it broadcasts the event to each session using `asyncio.gather`. After
broadcasting, it updates the stored message for three shorthand event types:

```python
if update_db:
    if "type" in event_data and event_data["type"] == "status":
        Chats.add_message_status_to_chat_by_id_and_message_id(...)
    if "type" in event_data and event_data["type"] == "message":
        ...  # fetch existing text and append
    if "type" in event_data and event_data["type"] == "replace":
        ...  # overwrite existing content
```
【F:external/open-webui/backend/open_webui/socket/main.py†L334-L366】

`status` entries append a status dict to the message's `statusHistory` list if
the message already exists. `message` events fetch the stored message (if any),
append the new chunk, and then call
`Chats.upsert_message_to_chat_by_id_and_message_id` to save the result. If no
message exists the update is skipped. `replace` overwrites the current text with
the provided content or creates the message if it doesn't already exist. Event types like `chat:completion` are
transient unless you persist them explicitly. When using the standard pipeline
this save happens automatically after the final chunk. If you emit
`chat:completion` events yourself, call `Chats.upsert_message_to_chat_by_id_and_message_id`
when you're done.

To emit without touching the database pass `False` when retrieving the emitter:

```python
emitter = get_event_emitter(metadata, False)
```

### Manual saves

Call `Chats.upsert_message_to_chat_by_id_and_message_id` whenever you need to
persist changes manually:

```python
Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, message_id, {"content": text})
```
【F:external/open-webui/backend/open_webui/models/chats.py†L228-L249】

### Custom metadata persistence

`Chats.upsert_message_to_chat_by_id_and_message_id` merges the provided
dictionary with any existing message data. Fields not mentioned remain
untouched, so you can store additional keys for your own use. Later
updates from the pipeline—such as the final `chat:completion` write—only
replace the built-in fields like `content` and preserve everything else.
This allows pipes to attach hidden state to a message and read it back in
subsequent turns.

The middleware may strip the `id` fields from the message list passed to
your pipe. To inspect prior metadata look up the stored history yourself:

```python
chat = Chats.get_chat_by_id(chat_id)
history = chat.chat.get("history", {})
msgs = history.get("messages", {})
chain = get_message_list(msgs, history.get("currentId")) or []
# ``chain[-1]`` is the incoming user message, ``chain[-2]`` the
# previous assistant reply
previous_meta = chain[-2].get("custom_meta") if len(chain) > 1 else None
```
## Common event types

| type                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `status`            | Progress or activity updates                          |
| `chat:message:delta`| Append streamed text to the current message           |
| `chat:message`      | Replace the current message content                   |
| `chat:completion`   | Send streamed completion chunks or final content      |
| `chat:message:files`| Attach or update message files                        |
| `chat:title`        | Update the conversation title                         |
| `chat:tags`         | Update conversation tags                              |
| `source`/`citation` | Add a citation or code execution result               |
| `notification`      | Show a toast notification                             |
| `confirmation`      | Ask for confirmation (requires `__event_call__`)      |
| `input`             | Request simple user input (requires `__event_call__`) |
| `execute`           | Run code client-side (requires `__event_call__`)      |

Custom event types may be used if the frontend knows how to handle them.

`message` and `replace` are backend shortcuts the UI treats as
`chat:message:delta` and `chat:message`. A similar alias `files` maps to
`chat:message:files`. Only `status`, `message` and `replace` trigger automatic
updates to the stored message. `chat:completion` events rely on the pipeline to
call `Chats.upsert_message_to_chat_by_id_and_message_id`.

## Examples

Emit a simple status update:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Processing started", "done": False}
})
```

Pause execution until the user confirms:

```python
result = await __event_call__({
    "type": "confirmation",
    "data": {"title": "Are you sure?", "message": "Proceed with action?"}
})
```

`result` will contain the user's answer or input value.

Stream chat completion text in chunks:

```python
await __event_emitter__(
    {
        "type": "chat:completion",
        "data": {"content": "partial text"},
    }
)
```

Send a final update when done and persist the full message:

```python
await __event_emitter__(
    {
        "type": "chat:completion",
        "data": {"done": True, "content": full_text},
    }
)
Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, message_id, {"content": full_text})
```

## Yielding text vs emitting events

A pipe may simply `yield` strings. Each value is converted to an SSE `data:` line by `functions.process_line` before being sent to the client. The UI appends the streamed text and no intermediate updates occur until the stream ends.

Using `__event_emitter__` lets you push partial content (`chat:message:delta`), status updates or attachments while streaming. These events reach all active sessions immediately and can update the database in real time if enabled.
Lines that begin with `data:` are also forwarded as `chat:completion` events over the WebSocket. Emitting events yourself gives full control over when each chunk is sent and persisted.
