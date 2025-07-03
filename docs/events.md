# Events: Communicating with the Frontend

Events allow backend components (**Pipes**, **Filters**, and **Tools**) to directly interact with Open WebUI’s frontend.

Two main helpers are used:

* **`__event_emitter__`** *(one-way communication)* sends immediate frontend updates.
* **`__event_call__`** *(two-way communication)* prompts the frontend and waits for user responses.

Basic structure for events:

```python
{
    "type": "<event_type>",
    "data": { ... }
}
```

---

## ✅ Example: Sending an Immediate Status Update

Use `__event_emitter__` to instantly notify the user of backend activity:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Fetching your data...", "done": False}
})
```

This updates the UI immediately.

---

## ✅ Example: Prompting User Confirmation

Use `__event_call__` to prompt the frontend and wait for the user's decision:

```python
confirmed = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Confirm Deletion",
        "message": "Are you sure you want to delete this item?"
    }
})

if confirmed:
    # Proceed with deletion
else:
    # Operation aborted by user
```

Backend logic pauses until a response is received.

---

## 📑 Supported Event Types

| Event Type                                       | Notes                                                                |
| ------------------------------------------------ | -------------------------------------------------------------------- |
| **`status`**                                     | Display incremental progress or status updates.                      |
| **`chat:message:delta`** / **`message`**         | Append incremental text (partial streaming results).                 |
| **`chat:message`** / **`replace`**               | Replace entire message content.                                      |
| **`chat:completion`**                            | Emit the final completed chat response.                              |
| **`chat:message:files`** / **`files`**           | Attach or update files in a message.                                 |
| **`chat:title`**                                 | Dynamically set/update the conversation title.                       |
| **`chat:tags`**                                  | Update tags associated with the conversation.                        |
| **`source`** / **`citation`**                    | Add references or citations to messages.                             |
| **`notification`**                               | Display toast notifications (`success`, `error`, `info`, `warning`). |
| **`confirmation`** *(requires `__event_call__`)* | Prompt user to confirm or cancel an action.                          |
| **`input`** *(requires `__event_call__`)*        | Prompt user for input and await their response.                      |
| **`execute`** *(requires `__event_call__`)*      | Execute client-side JavaScript and await the result.                 |

---

### Detailed Examples of Each Event Type

#### ✅ Status Updates (`status`)

Immediately inform users about backend processing states:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Loading results...", "done": False}
})
```

---

#### ✅ Incremental Text Updates (`chat:message:delta` or `message`)

Incrementally stream content to users (equivalent to yielding text although goes directly to frontend skipping middleware.py):

```python
await __event_emitter__({
    "type": "chat:message:delta",
    "data": {"content": "Processing step 1 of 3...\n"}
})
```

---

#### ✅ Full Message Replacement (`chat:message` or `replace`)

Replace entire chat message content instantly:

```python
await __event_emitter__({
    "type": "replace",
    "data": {"content": "Here's the final response to your query."}
})
```

---

#### ✅ Chat Completion (`chat:completion`)

Explicitly mark the completion of the chat:

```python
await __event_emitter__({
    "type": "chat:completion",
    "data": {"content": "Here's the final response to your query."}
})
```

---

#### ✅ Attaching Files (`chat:message:files` or `files`)

Attach files directly to a chat message:

```python
await __event_emitter__({
    "type": "files",
    "data": {"files": [{"name": "report.pdf", "url": "/files/report.pdf"}]}
})
```

---

#### ✅ Updating Conversation Title (`chat:title`)

Set or change the current chat title dynamically:

```python
await __event_emitter__({
    "type": "chat:title",
    "data": {"title": "Discussion about Event Emitters"}
})
```

---

#### ✅ Updating Conversation Tags (`chat:tags`)

Update tags associated with the current conversation:

```python
await __event_emitter__({
    "type": "chat:tags",
    "data": {"tags": ["python", "events", "examples"]}
})
```

---

#### ✅ Citations and Sources (`source` or `citation`)

Add references or citations to support your message:

```python
await __event_emitter__({
    "type": "citation",
    "data": {"sources": [{"title": "Event Docs", "url": "https://example.com/docs/events"}]}
})
```

---

#### ✅ Notifications (`notification`)

Display a toast notification on the user's screen:

```python
await __event_emitter__({
    "type": "notification",
    "data": {"kind": "success", "message": "Your data was successfully saved!"}
})
```

---

#### ✅ User Confirmation (`confirmation`) *(**event\_call** required)*

Prompt user confirmation and await response:

```python
confirmed = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Confirm Action",
        "message": "Do you want to proceed?"
    }
})

if confirmed:
    # continue action
else:
    # cancel action
```

---

#### ✅ User Input Prompt (`input`) *(**event\_call** required)*

Prompt user input and await their response:

```python
user_name = await __event_call__({
    "type": "input",
    "data": {"prompt": "Enter your name:"}
})
```

---

#### ✅ Executing JavaScript (`execute`) *(**event\_call** required)*

Execute client-side JavaScript and await result:

```python
result = await __event_call__({
    "type": "execute",
    "data": {"script": "return window.location.href;"}
})
```

---

## Integrating Events into Your Components

To use events, explicitly declare them in your component’s signature. Open WebUI automatically injects these helpers at runtime:

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

    # Continue processing...
```

Only parameters you explicitly declare will be injected.

---

## 🔧 Under the Hood: How Helpers Are Injected

When calling your component, Open WebUI internally prepares a dictionary (`extra_params`) containing available parameters. It dynamically inspects your function signature and only passes parameters you've explicitly defined.

Simplified internal example (`functions.py`):

```python
extra_params = {
    "__event_emitter__": get_event_emitter(metadata),
    "__event_call__": get_event_call(metadata),
    "__chat_id__": metadata.get("chat_id"),
    "__session_id__": metadata.get("session_id"),
    "__message_id__": metadata.get("message_id"),
}

# Pass only explicitly defined parameters:
sig = inspect.signature(function_module.pipe)
params = {k: v for k, v in extra_params.items() if k in sig.parameters}

result = await pipe(**params)
```

---

## 🛠️ Advanced: Creating Event Emitters Manually

You can manually create event helpers, although you'll need to specify the necessary metadata explicitly (`session_id`, `chat_id`, `message_id`):

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

## 🔄 Detailed Event Behavior

### Using `__event_emitter__` *(Broadcast)*

Events emitted via `__event_emitter__` broadcast to all active user sessions, including the current request's session, using Python Socket.IO.

These event types (`status`, `message`, `replace`) automatically persist in the database by default:

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Loading...", "done": False}
})
```

Disable automatic persistence if needed:

```python
emitter = get_event_emitter(metadata, update_db=False)
```

---

### Using `__event_call__` *(Await Response)*

`__event_call__` sends events specifically to the requesting session and waits synchronously for the user's response:

```python
user_input = await __event_call__({
    "type": "input",
    "data": {"prompt": "Enter your name:"}
})
```

Internally, this leverages Socket.IO’s `call` method, ensuring responses are bound to the correct user session.

---

## 🗄️ Event Persistence in Database

Here's a clearer restructuring with concise explanation and immediate examples:

---

## 🗄️ Event Persistence in Database

Some event types immediately persist to the database to protect against unexpected interruptions (e.g., the user closing their browser mid-stream). Others only update the browser's cached chat content and persist once the message is fully complete.

Events that automatically persist immediately include:

* **`status`**: Appends incremental updates to the message’s status history.
* **`message`**: Incrementally appends text content to the existing message.
* **`replace`**: Completely replaces the existing message content.

### Example: Manually Persisting Events

You can manually persist event data at any time by directly updating the database:

```python
Chats.upsert_message_to_chat_by_id_and_message_id(
    chat_id,
    message_id,
    {"content": new_content}
)
```

> **Note:**
> Manual persistence performed mid-stream may be overwritten by the frontend when the message completes.

---

## 🖥️ Frontend Integration

The frontend receives events via WebSocket and immediately updates UI state. Example from `Chat.svelte` component:

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
