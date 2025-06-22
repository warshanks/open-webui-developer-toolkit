# Events: `__event_emitter__` and `__event_call__`

Open WebUI extensions, tools, and pipes can push real-time updates directly to the user interface using two provided asynchronous helpers:

* **`__event_emitter__`**: Sends real-time events to all active sessions for the current user. *(Fire-and-forget)*
* **`__event_call__`**: Sends an event to the current user session and waits for the user's response. *(Awaitable)*

Both helpers expect a dictionary structured like this:

```python
{
    "type": "<event_type>",
    "data": { ... }
}
```

---

## Quick Examples

### Emit a status update to all user sessions:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Processing started", "done": False}
})
```

### Prompt the user and wait for confirmation:

```python
confirmed = await __event_call__({
    "type": "confirmation",
    "data": {"title": "Confirm Action", "message": "Proceed with action?"}
})

if confirmed:
    # Proceed with action
    ...
else:
    # Cancel action
    ...
```

---

## Detailed Behavior

### `__event_emitter__` (Broadcast)

When called, the emitter:

* Gathers all active user sessions, including the current request's session:

```python
session_ids = list(set(
    USER_POOL.get(user_id, []) +
    ([request_info.get("session_id")] if request_info.get("session_id") else [])
))
```

* Broadcasts the event to all sessions via Python Socket.IO.
* Optionally persists certain event types (`status`, `message`, `replace`) to the database by default (`update_db=True`).

### `__event_call__` (Await Response)

* Sends an event specifically to the current request session.
* Awaits the frontend response using `sio.call`:

```python
response = await sio.call(
    "chat-events",
    {
        "chat_id": request_info.get("chat_id"),
        "message_id": request_info.get("message_id"),
        "data": event_data,
    },
    to=request_info["session_id"]
)
```

---

## Database Persistence

The event emitter (`__event_emitter__`) automatically persists specific event types (`status`, `message`, `replace`) by default.

* **`status`**: Appends status updates to a message's `statusHistory`.
* **`message`**: Appends incremental text content to an existing message.
* **`replace`**: Replaces the entire message content or creates it if it doesn't exist.

To disable automatic persistence:

```python
emitter = get_event_emitter(metadata, update_db=False)
```

To manually persist changes:

```python
Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, message_id, {"content": new_content})
```

### Custom Metadata

Custom keys included in automatic events (`message`, `replace`) are ignored and not persisted. To save custom metadata, call explicitly:

```python
Chats.upsert_message_to_chat_by_id_and_message_id(
    chat_id, message_id, {"custom_meta": {"key": "value"}}
)
```

---

## Frontend Integration

The frontend listens for WebSocket events and updates in-memory chat state. (`Chat.svelte` component):

```svelte
$socket?.on('chat-events', chatEventHandler);

function chatEventHandler(event) {
    const { type, data } = event;

    if (type === 'chat:message:delta' || type === 'message') {
        message.content += data.content;
    } else if (type === 'chat:message' || type === 'replace') {
        message.content = data.content;
    }
}
```

---

## Common Event Types

| Event Type            | Description                                   |
| --------------------- | --------------------------------------------- |
| `status`              | Progress/activity updates                     |
| `chat:message:delta`  | Append streamed text chunks                   |
| `message`             | Append text content and persist               |
| `replace`             | Replace entire content and persist            |
| `chat:completion`     | Streamed completion text (manual persistence) |
| `chat:title`          | Update chat conversation title                |
| `chat:tags`           | Update conversation tags                      |
| `chat:message:files`  | Attach/update message files                   |
| `source` / `citation` | Add citations or results                      |
| `notification`        | Display notification to user                  |
| `confirmation`        | Prompt for confirmation (awaitable)           |
| `input`               | Prompt for user input (awaitable)             |
| `execute`             | Execute client-side code (awaitable)          |

* Only `status`, `message`, and `replace` persist automatically.
* Other events require explicit database updates if persistence is desired.

---

## Yielding Text vs Emitting Events

* **Yielding:** Directly stream text using `yield`. Streams via Server-Sent Events (SSE), minimal intermediate updates.
* **Emitting:** Send events with detailed control, enabling incremental updates, UI interactions, attachments, and persistence control.

---

## Real-Time Chat Saves

Controlled via `ENABLE_REALTIME_CHAT_SAVE`:

* **Enabled:** Each streamed chunk is persisted immediately.
* **Disabled (default):** Persistence occurs only upon completion.
