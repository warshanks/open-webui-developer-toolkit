# Message Execution Path

This document explains how a chat message travels from the user interface in `Chat.svelte` through the backend until it is stored in the database. Line numbers refer to the upstream snapshot in `external/open-webui`.

## 1. User submits a prompt

*Component:* [`Chat.svelte`](../external/open-webui/src/lib/components/chat/Chat.svelte)

1. **Message creation** – When the user presses **Send**, `handleSubmit` constructs a user message object starting at line 1406. The message includes `id`, `parentId`, `childrenIds`, `role`, `content`, optional `files` and timestamp fields.
2. **Add to local history** – Lines 1420–1425 insert the user message into `history.messages` and update `history.currentId`.
3. **Dispatch API call** – `sendPrompt` (lines 1437–1541) prepares assistant placeholder messages for each selected model and invokes `sendPromptSocket` for every model.

## 2. Sending the request

*Component:* `sendPromptSocket` function in [`Chat.svelte`](../external/open-webui/src/lib/components/chat/Chat.svelte)

1. **Build OpenAI payload** – Lines 1544–1667 collect chat history, merge files and build the OpenAI style `messages` array. Streaming preference and feature flags are included in the request body (lines 1636–1715).
2. **Outgoing request** – `generateOpenAIChatCompletion` is called (line 1636). This helper sends a POST request to `/api/chat/completions` using `fetch` as implemented in [`openai/index.ts`](../external/open-webui/src/lib/apis/openai/index.ts#L362-L386).
3. **Error handling** – If the fetch fails, `handleOpenAIError` stores the error in the placeholder message (lines 1718–1728 and 1747–1787).

## 3. Backend processing

1. **Route entry** – The backend exposes `POST /api/chat/completions` handled by [`chat_completion`](../external/open-webui/backend/open_webui/main.py#L1274-L1371). Authentication is enforced via `Depends(get_verified_user)`.
2. **Payload preparation** – `chat_completion` extracts `chat_id`, `id`, `session_id` and other fields into a `metadata` dictionary stored on `request.state`. It then calls `process_chat_payload` from [`utils/middleware.py`](../external/open-webui/backend/open_webui/utils/middleware.py#L720-L1034) which performs several transformations:
   - `apply_params_to_form_data` merges the request body with model‑specific parameters.
   - Event helpers (`__event_emitter__`, `__event_call__`) are created and bundled with user info in `extra_params`.
   - `process_pipeline_inlet_filter` and `process_filter_functions` run any enabled inlet filters which may mutate the request.
   - Feature handlers add memory, web search or image generation messages when requested.
   - Tools are resolved via `get_tools`; if native function calling is enabled the tool specs are inserted into `form_data["tools"]`, otherwise `chat_completion_tools_handler` runs them server side.
   - `chat_completion_files_handler` attaches file data and retrieval context; citations are collected into an `events` list for later emission.
   - The function returns the mutated `form_data`, the enriched `metadata` (now including `tool_ids`, `files`, etc.) and any pre‑generated events.
3. **Model dispatch** – `generate_chat_completion` from [`utils/chat.py`](../external/open-webui/backend/open_webui/utils/chat.py#L161-L328) chooses the appropriate model backend (OpenAI, Ollama, or pipe) and issues the completion request. Streaming responses are wrapped in `StreamingResponse` when applicable.

## 4. Response handling

1. **Process response** – After the model returns, `process_chat_response` in [`utils/middleware.py`](../external/open-webui/backend/open_webui/utils/middleware.py#L1036-L2410) handles both streaming and non‑streaming flows. It emits socket events (`chat:completion`, `status`) and can run background tasks for title or follow‑up generation.
2. **Update message** – The helper `Chats.upsert_message_to_chat_by_id_and_message_id` persists incremental message content as events arrive (example around line 2363). Final message data is stored once the stream ends.
3. **Save chat meta** – Background tasks such as title or tag generation update the chat document via `Chats.update_chat_title_by_id` and related methods.

## 5. Database persistence

The `Chats` model in [`models/chats.py`](../external/open-webui/backend/open_webui/models/chats.py#L150-L188) handles all chat storage. `upsert_message_to_chat_by_id_and_message_id` inserts or updates a message in the JSON chat history (lines 228–248). The entire chat is written back to the SQL database using `update_chat_by_id`.

## Side effects and events

* **Socket events** – `get_event_emitter` in [`socket/main.py`](../external/open-webui/backend/open_webui/socket/main.py#L304-L356) broadcasts `chat-events` to every active session for the user. Events such as `chat:start`, `chat:completion` and `status` allow the front‑end to update progress in real time.
* **Webhook notifications** – When the user is inactive, webhook hooks may be triggered in `process_chat_response` to deliver the message externally (lines 2338–2367).

## Error handling and edge cases

* Failed model requests raise HTTP 400 errors in `chat_completion`. Errors are embedded into the message record and emitted to clients.
* Streaming tasks are cancelled if the client disconnects (handled in `process_chat_response` lines 2350–2410).

## Summary

A single Send action results in:
1. Local message creation in the browser.
2. POST `/api/chat/completions` with the chat payload.
3. Backend pipeline and model invocation.
4. Incremental socket updates to the client.
5. Final message persistence via `Chats.upsert_message_to_chat_by_id_and_message_id` and `update_chat_by_id`.

