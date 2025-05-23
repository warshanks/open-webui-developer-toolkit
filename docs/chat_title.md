# Chat Title Generation

This note summarises how Open WebUI creates and updates chat titles.

## Backend endpoint

`backend/open_webui/routers/tasks.py` exposes a POST endpoint `/title/completions` that builds a prompt from recent messages and forwards it to the task model:

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

During a chat request, `process_chat_response` schedules a background task that calls `generate_title` once the main reply is done:

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

`editChatTitle` ultimately calls `updateChatById` through the `/chats/{id}` API endpoint.

## Retrieving a title

To fetch a chat including its title, use `GET /chats/{id}` which maps to `get_chat_by_id` in `routers/chats.py`.

### API example

```bash
GET /api/v1/chats/<chat_id>
```
The JSON response contains a `title` field alongside the `history` object.

## Programmatic access

Because pipes run inside the same process as WebUI you can import the `Chats`
helper to read or modify a title at any point:

```python
from open_webui.models.chats import Chats

current = Chats.get_chat_title_by_id(chat_id)
Chats.update_chat_title_by_id(chat_id, "My custom title")
```

When you set a title manually you normally want to stop the automatic generator
from overwriting it.  Pass `background_tasks: {"title_generation": false}` in the
request body or toggle the setting directly:

```python
old = __request__.app.state.config.ENABLE_TITLE_GENERATION
__request__.app.state.config.ENABLE_TITLE_GENERATION = False
try:
    # update titles during long running work
    ...
finally:
    __request__.app.state.config.ENABLE_TITLE_GENERATION = old
```

See `functions/pipes/dynamic_title_update_demo.py` for a minimal pipeline that
updates the title while it works.

---

**In short**: the backend generates a title asynchronously after each response, updates the database, and emits a `chat:title` event. The UI listens for this event to update its stores and the browser tab. Users can also trigger `/title/completions` manually via the sidebar button, which posts the chat messages and chosen model to the same endpoint.
