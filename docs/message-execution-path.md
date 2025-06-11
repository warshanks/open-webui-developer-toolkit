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
3. **Model dispatch** – `generate_chat_completion` in [`utils/chat.py`](../external/open-webui/backend/open_webui/utils/chat.py#L161-L286) merges `request.state.metadata` into the payload (lines 171–178) and then selects a backend:
   - *Direct connection* – when `request.state.direct` is set, `generate_direct_chat_completion` is called with the single model defined on the request (lines 180–197).
   - *Arena models* – aggregator models marked with `owned_by == "arena"` choose a random submodel (lines 206–252). The chosen ID replaces `form_data["model"]` and is streamed to the client when `stream=True` (lines 229–243).
   - *Custom pipes* – if the model includes a `pipe` entry, `generate_function_chat_completion` invokes the extension (lines 254–258).
   - *Ollama models* – payloads are converted via `convert_payload_openai_to_ollama` and sent to `generate_ollama_chat_completion`; streaming results are converted back using `convert_streaming_response_ollama_to_openai` (lines 260–276).
   - *Default OpenAI* – all remaining models call `generate_openai_chat_completion` (lines 277–283).
   
   `form_data` forwarded to the provider contains the target `model`, the message list, `stream` flag and any `tools` or metadata collected earlier.

## 4. Response handling

1. **Process response** – `process_chat_response` in [`utils/middleware.py`](../external/open-webui/backend/open_webui/utils/middleware.py#L1209-L2440) handles the HTTP result.
   - *Non‑streaming path* (lines 1209–1313) writes errors and the selected model to the database (lines 1212–1229) and, when content is present, emits a `chat:completion` event followed by `{done: True}` then persists the message (lines 1231–1265). Webhook notifications and optional background tasks are triggered afterwards (lines 1267–1283).
   - *Streaming path* begins at line 1337 where a task is created and the message record updated with the chosen model (lines 1338–1348). Pre-generated events are emitted and stored (lines 1718–1734). Streaming chunks are filtered and forwarded to clients while `Chats.upsert_message_to_chat_by_id_and_message_id` updates content incrementally when `ENABLE_REALTIME_CHAT_SAVE` is enabled (lines 1736–1994 and 1968–1981). When the stream ends a final `chat:completion` with the full content is sent and saved (lines 2320–2394). The whole handler runs as an async task scheduled via `create_task` (lines 2413–2416).
2. **Update message** – The helper `Chats.upsert_message_to_chat_by_id_and_message_id` persists incremental message content as events arrive (example around line 2363). Final message data is stored once the stream ends.
3. **Save chat meta** – Background tasks such as title or tag generation update the chat document via `Chats.update_chat_title_by_id` and related methods.

## 5. Database persistence

The `Chats` model in [`models/chats.py`](../external/open-webui/backend/open_webui/models/chats.py#L24-L40) defines the SQL `chat` table. Key columns include `id`, `user_id`, `title`, a JSON `chat` blob and timestamp fields. When `process_chat_response` stores an assistant reply it calls `Chats.upsert_message_to_chat_by_id_and_message_id` (lines 228–249). This helper updates `chat["history"]["messages"][message_id]` and sets `history["currentId"]` before delegating to `update_chat_by_id` (lines 161–172) which commits the row.

Fields persisted for each message include:

* `role`, `content` and any `files`
* model identifiers (`model`, `selectedModelId`)
* metadata such as `followUps` or tool results
* the timestamp from the original user payload

During streaming, chunks are written incrementally when `ENABLE_REALTIME_CHAT_SAVE` is enabled (lines 1971–1981). Otherwise the final content replaces the placeholder once the stream ends (lines 2361–2367). Each call to `update_chat_by_id` updates the `updated_at` column.

Failure of any write returns `None` from these helpers; no rollback is performed and the latest successful state remains.

## Side effects and events

* **Socket events** – `get_event_emitter` in [`socket/main.py`](../external/open-webui/backend/open_webui/socket/main.py#L304-L371) broadcasts `chat-events` to all active sessions. When `update_db=True` it also persists `status`, `message` and `replace` events (lines 334–369).
* **Background tasks** – After the final message is saved, `background_tasks_handler` may invoke `generate_follow_ups`, `generate_title` and `generate_chat_tags` (lines 1008–1194). These update the chat via `Chats.update_chat_title_by_id` (lines 1136–1147) or `Chats.update_chat_tags_by_id` (lines 1183–1192) and emit `chat:title`, `chat:tags` or `chat:message:follow_ups` events.
* **Webhook notifications** – When the user is inactive a `post_webhook` call notifies them with the final content (lines 2371–2385).
* **Task scheduling** – Streaming handlers run in an async task created via `create_task` (lines 2413–2416). If cancelled, the last content is persisted (lines 2399–2407).

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

