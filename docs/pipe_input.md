# Pipe Input Reference

This document summarizes the data structures passed to a pipe's `pipe()` method. Each argument is described in its own section so automated tools can easily locate the information they need.

## Function Signature

```python
async def pipe(
    self,
    body: dict[str, Any],
    __user__: dict[str, Any],
    __request__: Request,
    __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
    __event_call__: Callable[[dict[str, Any]], Awaitable[Any]],
    __files__: list[dict[str, Any]],
    __metadata__: dict[str, Any],
    __tools__: dict[str, Any],
) -> AsyncIterator[str]:
    ...
```

The pipe receives a JSON-like payload describing the chat request (`body`) plus several helper objects such as user info and metadata. The pipe yields its response text as an asynchronous stream.

## 1. `body`

Holds the conversation request. Typical keys include:

* `stream` – `true` for partial streaming.
* `model` – the model identifier, e.g. `"openai_responses.gpt-4.1"`.
* `messages` – list of `{role, content}` chat messages.
* `stream_options` – options such as `include_usage: true`.
* `tools` – list of tool/function definitions.

Example:

```jsonc
{
  "stream": true,
  "model": "openai_responses.gpt-4.1",
  "messages": [
    {"role": "system", "content": "System prompt text..."},
    {"role": "user", "content": "User question..."}
  ],
  "stream_options": {"include_usage": true},
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "calculator",
        "description": "Accurate math expressions, etc.",
        "parameters": {
          "type": "object",
          "properties": {
            "expression": {"type": "string", "description": "..."}
          },
          "required": ["expression"]
        }
      }
    }
  ]
}
```

## 2. `__user__`

Information about the current user. Common keys:

* `id` – user UUID
* `email` – email address
* `name` – full or display name
* `role` – role such as `admin` or `user`
* `valves` – optional flag string enabling features or logging

Example:

```jsonc
{
  "id": "91216674-177d-4d5b-8a0b-a2d83783eb54",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "admin",
  "valves": "CUSTOM_LOG_LEVEL='DEBUG' ..."
}
```

## 3. `__request__`

The FastAPI `Request` object for the incoming HTTP call. A pipe can read headers or query parameters from here if needed.

## 4. `__event_emitter__` and `__event_call__`

Async callbacks to emit events or invoke additional workflow steps. Pipes that do not use events can safely ignore them.

## 5. `__files__`

List of uploaded file metadata. Each entry contains a `type` (usually `file`) and a nested `file` object with details such as `filename`, `hash`, and `data.content`.

Example:

```jsonc
[
  {
    "type": "file",
    "file": {
      "id": "c84fc997-c695-45f1-b031-258a26a95f3b",
      "user_id": "91216674-177d-4d5b-8a0b-a2d83783eb54",
      "hash": "...",
      "filename": "document.pdf",
      "data": {"content": "<base64 or text content>"},
      "meta": {
        "name": "document.pdf",
        "content_type": "application/pdf",
        "size": 123456,
        "data": {},
        "collection_name": "file-c84fc997-c695-..."
      },
      "created_at": 1747960134,
      "updated_at": 1747960134
    },
    "id": "c84fc997-c695-45f1-b031-258a26a95f3b",
    "url": "/api/v1/files/c84fc997-c695-45f1-b031-258a26a95f3b",
    "name": "document.pdf",
    "collection_name": "file-c84fc997-c695-45f1-b031-258a26a95f3b",
    "status": "uploaded",
    "size": 123456,
    "error": "",
    "itemId": "6d4fe4ad-e79f-4732-9564-c0031ca73dbe"
  }
]
```

## 6. `__metadata__`

Additional identifiers and settings for the conversation. Useful keys:

* `user_id`, `chat_id`, `message_id`, `session_id`
* `filter_ids`, `tool_ids`, `tool_servers`
* `features` – toggles such as `image_generation` or `web_search`
* `variables` – placeholders like `{{CURRENT_DATE}}`
* `model` – detailed model configuration

Example:

```jsonc
{
  "user_id": "91216674-177d-4d5b-8a0b-a2d83783eb54",
  "chat_id": "98ae8607-32df-411a-bd49-0dd56f55c1a5",
  "message_id": "7f4d7ae8-1140-4383-8777-340cfdf0774e",
  "session_id": "SLVt0Uz8iSQ8EzkeAABD",
  "filter_ids": [],
  "tool_ids": ["calculator"],
  "tool_servers": [],
  "files": null,
  "features": {
    "image_generation": false,
    "code_interpreter": false,
    "web_search": false
  },
  "variables": {
    "{{USER_NAME}}": "Alice",
    "{{CURRENT_DATETIME}}": "2025-05-22 17:18:33"
  },
  "model": {
    "id": "openai_responses.gpt-4.1",
    "name": "OpenAI: GPT-4.1 (Preview)"
  },
  "actions": [],
  "filters": [
    {
      "id": "web_search_toggle_filter",
      "name": "Web Search",
      "description": "Enable GPT-4o Search Preview...",
      "icon": "<icon data>"
    }
  ],
  "tags": [{"name": "Base Model"}]
}
```

## 7. `__tools__`

Dictionary of tool definitions keyed by tool name. Each entry typically includes a `tool_id`, `callable`, `spec` describing parameters, and optional metadata.

Example:

```jsonc
{
  "calculator": {
    "tool_id": "calculator",
    "callable": "<function Tools.calculator at 0x12345>",
    "spec": {
      "name": "calculator",
      "description": "Accurate math expressions...",
      "parameters": {
        "type": "object",
        "properties": {
          "expression": {
            "type": "string",
            "description": "A SymPy-compatible math expression."
          }
        },
        "required": ["expression"]
      }
    },
    "metadata": {"file_handler": false, "citation": false}
  }
}
```
