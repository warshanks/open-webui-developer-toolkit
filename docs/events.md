# Events: Communicating with the Frontend

Events enable backend Pipes, Filters, and Tools to directly interact with Open WebUI’s frontend. They come in two forms:

* **`__event_emitter__`** *(one-way)*: Sends immediate updates to the frontend.
* **`__event_call__`** *(two-way)*: Prompts the frontend and awaits a user response.

Both helpers expect a dictionary structured like this:

```python
{
    "type": "<event_type>",
    "data": { ... }
}
```

---

## 🚩 Two Basic Examples to Get You Started

### ✅ Example 1: Sending a simple status update

Use the `__event_emitter__` helper to quickly notify the frontend of progress:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Fetching your data...", "done": False}
})
```

This immediately updates the UI to show the status message.

---

### ✅ Example 2: Asking the user for confirmation

Use the `__event_call__` helper to prompt the user and wait for their response:

```python
confirmed = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Confirm Deletion",
        "message": "Are you sure you want to delete this item?"
    }
})

if confirmed:
    # User confirmed: proceed with deletion
else:
    # User canceled: abort operation
```

This pauses your backend logic until the user responds.

---

## 📑 Supported Event Types

| Type                                             | Data Example                                               | Notes                                                             |
| ------------------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------------------------- |
| **`status`**                                     | `{"description": "Loading...", "done": False}`             | Display incremental progress or status updates.                   |
| **`chat:message:delta`** / **`message`**         | `{"content": "Partial response..."}`                       | Append incremental text (for streaming partial results).          |
| **`chat:message`** / **`replace`**               | `{"content": "Full message content."}`                     | Fully replace the current message content.                        |
| **`chat:completion`**                            | *(Same format as `chat:message`, typically final output.)* | Emit the final completed chat response.                           |
| **`chat:message:files`** / **`files`**           | `{"files": [/* file objects */]}`                          | Attach files to the current message.                              |
| **`chat:title`**                                 | `{"title": "Project Planning Session"}`                    | Dynamically update the conversation title.                        |
| **`chat:tags`**                                  | `{"tags": ["urgent", "project"]}`                          | Update tags associated with the conversation.                     |
| **`source`** / **`citation`**                    | `{/* citation object */}`                                  | Add references or source citations to messages.                   |
| **`notification`**                               | `{"type": "success", "content": "Saved successfully!"}`    | Show toast notifications (`success`, `error`, `info`, `warning`). |
| **`confirmation`** *(requires `__event_call__`)* | `{"title": "Confirm Action", "message": "Proceed?"}`       | Prompt the user to confirm or cancel an action.                   |
| **`input`** *(requires `__event_call__`)*        | `{"title": "Enter Name", "placeholder": "John Doe"}`       | Prompt user for text input and await response.                    |
| **`execute`** *(requires `__event_call__`)*      | `{"code": "alert('Hello, World!');"}`                      | Execute client-side JavaScript and await the result.              |

---

## Adding Events to Your Pipe, Filter, or Tool

To use events, add `__event_emitter__` and/or `__event_call__` as optional parameters to your pipe's definition. Open WebUI detects these parameters and automatically injects them when calling your function:

### Example Pipe Definition:

```python
async def pipe(
    self,
    body: dict,
    __event_emitter__: Callable[[dict], Awaitable[None]] = None,
    __event_call__: Callable[[dict], Awaitable[Any]] = None,
):
    await __event_emitter__({
        "type": "status",
        "data": {"description": "Processing started...", "done": False}
    })

    confirmed = await __event_call__({
        "type": "confirmation",
        "data": {"message": "Continue operation?"}
    })

    if not confirmed:
        return {"error": "Operation cancelled by user"}

    # Continue with pipe logic...
```

---

### How __event_emitter__ and __event_call__ and created ("Under the Hood")

When invoking your pipe, Open WebUI builds an internal dictionary called `extra_params`. It then dynamically inspects your pipe’s function signature and only passes in parameters you explicitly request.

Here’s a simplified internal snippet (from `functions.py`):

```python
extra_params = {
    "__event_emitter__": get_event_emitter(metadata),
    "__event_call__": get_event_call(metadata),
    "__chat_id__": metadata.get("chat_id"),
    "__session_id__": metadata.get("session_id"),
    "__message_id__": metadata.get("message_id"),
    "__user__": user.model_dump(),
    "__metadata__": metadata,
    "__files__": metadata.get("files", []),
}

# Inspect your pipe signature and pass matching params only:
sig = inspect.signature(function_module.pipe)
params = {k: v for k, v in extra_params.items() if k in sig.parameters}

# Finally, invoke your pipe with these parameters:
result = await pipe(**params)
```

**Key takeaway:**
Open WebUI only passes parameters you explicitly declare. It's also worth noting that not all parameters are available everywhere—some vary based on context. For instance, filters have different parameters accessible at their inlet compared to their outlet. In this guide, we specifically focus on `__event_emitter__` and `__event_call__`, both of which are consistently available in pipes, filters, and tools.

### Creating Events Manually (Advanced):
You can technically manually build event emitters and calls instead of relying on Open WebUI to pass `__event_emitter__` and `__event_call__`.  Example below.  Although you would need to specify the session_id, chat_id and message_id so the event emitter/call can be bound to the write frontend session/message.

```python
from open_webui.socket.main import get_event_emitter, get_event_call

metadata = {
    "session_id": "user-session-id",
    "chat_id": "chat-id",
    "message_id": "message-id"
}

event_emitter = get_event_emitter(metadata)
event_call = get_event_call(metadata)
```
---



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
