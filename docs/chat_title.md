# Chat Title Generation

This note summarises how Open WebUI creates and updates chat titles.

## Backend endpoint

`backend/open_webui/routers/tasks.py` exposes a POST endpoint `/title/completions` (served under the `/api/v1/tasks` prefix) that builds a prompt from recent messages and forwards it to the task model:

```python
@router.post("/title/completions")
async def generate_title(request: Request, form_data: dict, user=Depends(get_verified_user)):
    ...
    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            ...,
            "task": str(TASKS.TITLE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }
    return await generate_chat_completion(request, form_data=payload, user=user)
```
【F:external/open-webui/backend/open_webui/routers/tasks.py†L143-L231】

The handler constructs a prompt using `title_generation_template` and sends it to `generate_chat_completion`. The response contains a JSON block like `{ "title": "..." }`.

## Background task

During a chat request, `process_chat_response` starts a background task after the main reply is sent. This task calls `generate_title` and updates the title:

```python
if tasks and messages:
    if TASKS.TITLE_GENERATION in tasks:
        if tasks[TASKS.TITLE_GENERATION]:
            res = await generate_title(request, {...}, user)
            ...
            Chats.update_chat_title_by_id(metadata["chat_id"], title)
            await event_emitter({"type": "chat:title", "data": title})
        elif len(messages) == 2:
            title = messages[0].get("content", "New Chat")
            Chats.update_chat_title_by_id(metadata["chat_id"], title)
            await event_emitter({"type": "chat:title", "data": message.get("content", "New Chat")})
```
【F:external/open-webui/backend/open_webui/utils/middleware.py†L983-L1038】

This updates the database via `Chats.update_chat_title_by_id` and emits a `chat:title` websocket event so the frontend refreshes the chat list.

## Database helper

`Chats.update_chat_title_by_id` writes the new title back to the stored chat JSON:

```python
def update_chat_title_by_id(self, id: str, title: str) -> Optional[ChatModel]:
    chat = self.get_chat_by_id(id)
    if chat is None:
        return None
    chat = chat.chat
    chat["title"] = title
    return self.update_chat_by_id(id, chat)
```
【F:external/open-webui/backend/open_webui/models/chats.py†L175-L183】

## Frontend behaviour

`chatTitle` is a writable store used across the UI:

```ts
export const chatId = writable('');
export const chatTitle = writable('');
```
【F:external/open-webui/src/lib/stores/index.ts†L46-L48】

When a `chat:title` event arrives, the current page and chat list are refreshed:

```svelte
} else if (type === 'chat:title') {
    chatTitle.set(data);
    currentChatPage.set(1);
    await chats.set(await getChatList(localStorage.token, $currentChatPage));
}
```
【F:external/open-webui/src/lib/components/chat/Chat.svelte†L288-L296】

The page `<title>` element binds to `$chatTitle` so the browser tab updates automatically:

```svelte
<svelte:head>
    <title>
        {$chatTitle ? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} • ${$WEBUI_NAME}` : `${$WEBUI_NAME}`}
    </title>
</svelte:head>
```
【F:external/open-webui/src/lib/components/chat/Chat.svelte†L1978-L1984】

When sending a new message the frontend decides whether to run title generation
by including a `background_tasks` block with the request:

```svelte
background_tasks: {
    title_generation: $settings?.title?.auto ?? true,
    tags_generation: $settings?.autoTags ?? true
}
```
【F:external/open-webui/src/lib/components/chat/Chat.svelte†L1688-L1704】

### Manual title generation

Each chat row in the sidebar has a "Generate" button that calls the task endpoint and then updates the title:

```svelte
const generateTitleHandler = async () => {
    generating = true;
    if (!chat) {
        chat = await getChatById(localStorage.token, id);
    }
    const messages = (chat.chat?.messages ?? []).map((message) => ({
        role: message.role,
        content: message.content
    }));
    const model = chat.chat.models.at(0) ?? chat.models.at(0) ?? '';
    chatTitle = '';
    const generatedTitle = await generateTitle(localStorage.token, model, messages).catch((error) => {
        toast.error(`${error}`);
        return null;
    });
    if (generatedTitle) {
        if (generatedTitle !== title) {
            editChatTitle(id, generatedTitle);
        }
        confirmEdit = false;
    } else {
        chatTitle = title;
    }
    generating = false;
};
```
【F:external/open-webui/src/lib/components/layout/Sidebar/ChatItem.svelte†L229-L264】

`editChatTitle` ultimately calls `updateChatById` through the `/api/v1/chats/{id}` API endpoint.

## Retrieving a title

To fetch a chat including its title, use `GET /api/v1/chats/{id}` which maps to `get_chat_by_id` in `routers/chats.py`.

### API example

```bash
GET /api/v1/chats/<chat_id>
```
The JSON response contains a `title` field alongside the `history` object.

## Programmatic access

Pipes and other Python code run in the same process can call helper methods to
read or update the title directly:

```python
from open_webui.models.chats import Chats

current = Chats.get_chat_title_by_id(chat_id)
Chats.update_chat_title_by_id(chat_id, "Processing...")
```
【F:external/open-webui/backend/open_webui/models/chats.py†L175-L214】

## Updating the title from a pipe

A custom pipe can persist a title and notify the UI at run time. Use
`Chats.update_chat_title_by_id` together with `__event_emitter__`. Disable
automatic generation in the request to keep your value:

```python
from typing import Any, AsyncIterator, Callable, Awaitable, Dict
from fastapi import Request
from open_webui.models.chats import Chats

class Pipe:
    async def pipe(
        self,
        body: Dict[str, Any],
        __request__: Request,
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __metadata__: Dict[str, Any],
        **_,
    ) -> AsyncIterator[str]:
        chat_id = __metadata__.get("chat_id")
        title = f"Result for {body['messages'][-1]['content'][:20]}"
        Chats.update_chat_title_by_id(chat_id, title)
        await __event_emitter__({"type": "chat:title", "data": title})
        body.setdefault("background_tasks", {})["title_generation"] = False
        yield "..."
```

To temporarily disable generation for the same request without editing the
payload, wrap your call with:

```python
original = __request__.app.state.config.ENABLE_TITLE_GENERATION
__request__.app.state.config.ENABLE_TITLE_GENERATION = False
try:
    ...
  finally:
      __request__.app.state.config.ENABLE_TITLE_GENERATION = original
```

### Progress updates

Long-running tasks can update the title multiple times to show progress. The
pipe below emits "Processing 1/3", "Processing 2/3" and so on before finishing
with "Task Complete":

```python
import asyncio
from typing import Any, AsyncIterator, Callable, Awaitable, Dict
from fastapi import Request
from open_webui.models.chats import Chats

class Pipe:
    async def pipe(
        self,
        body: Dict[str, Any],
        __request__: Request,
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __metadata__: Dict[str, Any],
        **_,
    ) -> AsyncIterator[str]:
        chat_id = __metadata__.get("chat_id")
        body.setdefault("background_tasks", {})["title_generation"] = False

        for step in range(1, 4):
            title = f"Processing {step}/3"
            Chats.update_chat_title_by_id(chat_id, title)
            await __event_emitter__({"type": "chat:title", "data": title})
            await asyncio.sleep(0.1)
            yield f"Step {step} done\n"

        final_title = "Task Complete"
        Chats.update_chat_title_by_id(chat_id, final_title)
        await __event_emitter__({"type": "chat:title", "data": final_title})
        yield "All done"
```

## Manual updates via API

The sidebar’s "Edit" button calls `updateChatById` to persist a custom title. The
Svelte component posts to `/api/v1/chats/{id}` with a new `title` field:

```svelte
const editChatTitle = async (id, title) => {
        if (title === '') {
                toast.error($i18n.t('Title cannot be an empty string.'));
        } else {
                await updateChatById(localStorage.token, id, {
                        title: title
                });
                if (id === $chatId) {
                        _chatTitle.set(title);
                }
                currentChatPage.set(1);
                await chats.set(await getChatList(localStorage.token, $currentChatPage));
                await pinnedChats.set(await getPinnedChatList(localStorage.token));
                dispatch('change');
        }
};
```
【F:external/open-webui/src/lib/components/layout/Sidebar/ChatItem.svelte†L71-L92】

The helper function itself issues a POST request to `/api/v1/chats/<id>`:

```ts
export const updateChatById = async (token: string, id: string, chat: object) => {
        let error = null;
        const res = await fetch(`${WEBUI_API_BASE_URL}/chats/${id}`, {
                method: 'POST',
                headers: {
                        Accept: 'application/json',
                        'Content-Type': 'application/json',
                        ...(token && { authorization: `Bearer ${token}` })
                },
                body: JSON.stringify({
                        chat: chat
                })
        })
                .then(async (res) => {
                        if (!res.ok) throw await res.json();
                        return res.json();
                })
                .catch((err) => {
                        error = err;
                        console.error(err);
                        return null;
                });
        if (error) {
                throw error;
        }
        return res;
};
```
【F:external/open-webui/src/lib/apis/chats/index.ts†L788-L829】

## Sending a `chat:title` event

After generating a title, the backend updates the database and broadcasts a
websocket event so connected clients refresh the sidebar:

```python
Chats.update_chat_title_by_id(metadata["chat_id"], title)
await event_emitter({
    "type": "chat:title",
    "data": title,
})
```
【F:external/open-webui/backend/open_webui/utils/middleware.py†L1016-L1033】

Note that `event_emitter` only updates stored messages for certain event types
("status", "message", "replace"). It does **not** persist `chat:title` on its own:

```python
        if update_db:
            if "type" in event_data and event_data["type"] == "status":
                Chats.add_message_status_to_chat_by_id_and_message_id(...)

            if "type" in event_data and event_data["type"] == "message":
                ...

            if "type" in event_data and event_data["type"] == "replace":
                ...
```
【F:external/open-webui/backend/open_webui/socket/main.py†L324-L385】

To emit a title change without background tasks, call `send_chat_message_event_by_id`
with `{"type": "chat:title", "data": "New Title"}` and separately update the
database via `updateChatById` or `Chats.update_chat_title_by_id`.

## Configuration

Title generation runs only when `ENABLE_TITLE_GENERATION` is true. The flag is
loaded into the application state during startup:

```python
app.state.config.ENABLE_TITLE_GENERATION = ENABLE_TITLE_GENERATION
```
【F:external/open-webui/backend/open_webui/main.py†L910-L913】

Administrators can toggle this via the interface settings where
`taskConfig.ENABLE_TITLE_GENERATION` binds to a UI switch:

```svelte
<Switch bind:state={taskConfig.ENABLE_TITLE_GENERATION} />
```
【F:external/open-webui/src/lib/components/admin/Settings/Interface.svelte†L212-L215】


To prevent the background task from overwriting your custom title in the same
request disable it via the payload:

```json
"background_tasks": { "title_generation": false }
```
or temporarily toggle `__request__.app.state.config.ENABLE_TITLE_GENERATION`.

---

**In short**: the backend generates a title asynchronously after each response, updates the database, and emits a `chat:title` event. The UI listens for this event to update its stores and the browser tab. Users can also trigger `/api/v1/tasks/title/completions` manually via the sidebar button, which posts the chat messages and chosen model to the same endpoint.
