# Open WebUI Chat Persistence Notes

This document summarizes how chat messages are stored in the upstream Open WebUI project based on a review of the source code.

## Chat history structure
- Each row in the `chat` table has a JSON column named `chat`.
- Chat history lives under `chat["history"]` which contains:
  - `currentId` – the latest message id.
  - `messages` – a dictionary mapping message ids to message objects.
- Messages typically include `id`, `parentId`, `role` and `content`. The `content` field is either a string or a list of typed blocks (e.g. `{type: "text", text: "hi"}`).

## `upsert_message_to_chat_by_id_and_message_id`
- Located in `backend/open_webui/models/chats.py`.
- Merges the provided dictionary into the existing message entry or creates a new one.
- There is no schema validation – arbitrary keys are stored as given.
- Custom fields added to a message dictionary will therefore persist
  in the database. They may be ignored by the default UI unless
  additional code knows how to handle them.

## Middleware serialization
- `backend/open_webui/utils/middleware.py` builds messages from `content_blocks`.
- Tool calls and code interpreter output are embedded inside the `content` string using `<details type="tool_calls">` or `<details type="code_interpreter">` tags.
- `convert_content_blocks_to_messages` converts a list of blocks to message objects. When a `tool_calls` block is encountered it emits:
  ```python
  {
      "role": "assistant",
      "content": serialize_content_blocks(temp_blocks),
      "tool_calls": block.get("content"),
  }
  ```
  followed by tool results as separate `{"role": "tool", ...}` entries.

## Observations
- The database persists any extra keys but most helpers only read `role`, `content` and sometimes `files`.
- Embedding tool metadata directly inside `content` is how the UI displays call progress. Standalone fields like `tool_calls` are ignored by the renderer unless custom code processes them.
- Final message writes from the middleware overwrite `content` but keep previously stored fields due to the merge logic.
