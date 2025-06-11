# OpenAI Responses Manifold
**Enables advanced OpenAI features (function calling, tool use, web search, visible reasoning summaries, and more) directly in [Open WebUI](https://github.com/open-webui/open-webui).**

> **Author:** [Justin Kropp](https://github.com/jrkropp)  
> **License:** MIT

⚠️ **Version 0.7.0 – Pre‑production preview.** The pipe (manifold) is still under early testing and will be fully released as `1.0.0`.

## Installation
1. Copy `openai_responses_manifold.py` to your Open WebUI under **Admin Panel ▸ Functions**.
2. Enable the pipe and configure the valves for your environment.

## Features

| Feature | Status | Last updated | Notes |
| --- | --- | --- | --- |
| Native function calling | ✅ GA | 2025-06-04 | Automatically enabled for supported models. |
| Visible reasoning summaries | ✅ GA | 2025-06-03 | Available for o‑series models only. |
| Encrypted reasoning tokens | ✅ GA | 2025-06-03 | Persists reasoning context across turns. |
| Optimized token caching | ✅ GA | 2025-06-03 | Save up to ~50–75 % on supported models. |
| Web search tool | ✅ GA | 2025-06-03 | Automatically invoked or toggled manually. |
| Task model support | ✅ GA | 2025-06-06 | Use model as [Open WebUI External Task Model](https://docs.openwebui.com/tutorials/tips/improve-performance-local/) (title generation, tag generation, etc.). |
| Streaming responses (SSE) | ✅ GA | 2025-06-04 | Real-time, partial output streaming for text and tool events. |
| Usage Pass-through | ✅ GA | 2025-06-04 | Tokens and usage aggregated and passed through to Open WebUI GUI. |
| Truncation control | ✅ GA | 2025-06-10 | Valve `TRUNCATION` sets the responses `truncation` parameter (auto or disabled). Works with per-model `max_completion_tokens`. |
| Image input (vision) | 🔄 In-progress | 2025-06-03 | Pending future release. |
| Image generation tool | 🕒 Backlog | 2025-06-03 | Incl. multi-turn image editing (e.g., upload and modify). |
| File upload / file search tool | 🕒 Backlog | 2025-06-03 | Roadmap item. |
| Code interpreter tool | 🕒 Backlog | 2025-06-03 | [OpenAI docs](https://platform.openai.com/docs/guides/tools-code-interpreter) |
| Computer use tool | 🕒 Backlog | 2025-06-03 | [OpenAI docs](https://platform.openai.com/docs/guides/tools-computer-use) |
| Live conversational voice (Talk) | 🕒 Backlog | 2025-06-03 | Requires backend patching; design under consideration. |
| Dynamic chat titles | 🕒 Backlog | 2025-06-03 | For progress/status indication during long tasks. |
| MCP tool support | 🕒 Backlog | 2025-06-09 | Remote MCP servers via Responses API. [More info](https://platform.openai.com/docs/guides/tools-remote-mcp) |


### Other Features
- **Pseudo-models**: `o3-mini-high` / `o4-mini-high` – alias for `o3-mini` / `o4-mini` with high reasoning effort.
- **Debug logging**: Set `LOG_LEVEL` to `debug` for in‑message log details. Can be set globally or per user.
- **Truncation strategy**: Control with the `TRUNCATION` valve. Default `auto` drops middle context when the request exceeds the window; `disabled` fails with a 400 error. Works with each model's `max_completion_tokens` limit.

### Tested models
The manifold should work with any model that supports the responses API. Confirmed with:
| Model ID | Status |
| --- | --- |
| chatgpt-4o-latest | ✅ |
| codex-mini-latest | ✅ |
| gpt-4.1 | ✅ |
| gpt-4o | ✅ |
| o3 | ✅ |
| o3-pro | ✅ |

# How it Works / Design Architecture
## Core concepts
- **Responses API endpoint** – uses the OpenAI Responses API endpoint than completions, enabling features like visible reasoning summaries and built-in tools (web search, etc..).
- **Persistent tool results** – tool outputs are stored alongside messages, making them available on later turns.
- **Encrypted reasoning tokens** – specialized reasoning tokens (`encrypted_content`) are persisted to optimize follow‑ups.


## Persist OpenAI response items
Non-message items (function calls, encrypted reasoning tokens and so on) are stored under `openai_responses_pipe` within the chat record. Keeping these items allows the pipe to reconstruct the conversation state precisely, leading to better caching and faster responses.

This design matters for two main reasons:

1. **Improved caching and cost efficiency** – reconstructing the original context lets OpenAI grant cache-based pricing discounts (up to 75 %!).
2. **Faster replies** – reasoning tokens prevent the model from re-solving earlier steps, so responses are quicker.

You can inspect this data by opening **Developer Tools** and examining the POST request for a chat in the **Network** tab.

Full chat JSON structure example:

```json
{
  "id": "<chat_id>",
  "user_id": "<user_id>",
  "title": "<chat_title>",
  "chat": {
    "id": "<chat_internal_id>",
    "title": "<chat_title>",
    "models": ["<model_id>"],
    "params": {},
    "history": {
      "messages": {
        "<message_id>": {
          "id": "<message_id>",
          "parentId": "<parent_message_id_or_null>",
          "childrenIds": ["<child_message_id>", "..."],
          "role": "user|assistant|function",
          "content": "<message_text_or_null>",
          "model": "<model_id>",
          "modelName": "<model_display_name>",
          "modelIdx": <index>,
          "timestamp": <unix_ms>,
          "usage": {},
          "done": true
        }
      },
      "currentId": "<current_message_id>"
    },
    "messages": [
      {
        // Flattened version of messages
      }
    ],
    "tags": ["<optional_tag>", "..."],
    "timestamp": <unix_ms>,
    "files": [
      // Any attached files
    ],

    // —— Custom Extension: Added by openai_responses_pipe ——
    "openai_responses_pipe": {
      "__v": 2,
      "messages": {
        "<message_id>": {
          "model": "<model_that_generated_nonmessage_items>",
          "created_at": <unix_timestamp>,
          "items": [
            {
              "type": "function_call|function_call_result|reasoning|...",
              "...": "..."
            }
          ]
        }
      }
    }
    // —————————————————
  },
  "updated_at": <unix_timestamp>,
  "created_at": <unix_timestamp>,
  "share_id": null,
  "archived": false,
  "pinned": false,
  "meta": {},
  "folder_id": null
}
```

Each item is tied to a specific `message_id` and the `model` that generated it. This ensures:

1. **Accurate Context Reconstruction**
   During replay or follow‑up turns, the pipe can precisely rebuild the state of the conversation, including tools or reasoning results not visible in plain messages.
2. **Model‑Specific Binding**
   Some items (especially **encrypted reasoning tokens!**) can only be used with the exact model that produced them. Injecting these into another model’s context may result in **errors** or degraded performance. Binding items to the generating model avoids this.

By storing raw `items` exactly as received from the API, the system remains forward‑compatible with future changes to the Responses API structure.
