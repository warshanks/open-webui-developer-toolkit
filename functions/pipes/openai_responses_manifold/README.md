# OpenAI Responses Manifold

A pipeline integrating OpenAI's Responses API into Open WebUI, exposing various advanced OpenAI features like web search tool, visible reasoning summaries, etc... that are ONLY available via the Responses API.

## Installation

1. Copy `openai_responses_manifold.py` to your Open WebUI under **Admin ▸ Pipelines**.
2. Activate and configure valves as needed.

---

### Features

| **Feature**                 | **Status** | **Notes**                                                                                                     |
| --------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------- |
| Native function calling     | ✅ GA       | Enable with `ENABLE_NATIVE_TOOL_CALLING`.                                                                     |
| Visible reasoning summaries | ✅ GA       | Insight into *o-series* model thinking (Responses API only).                                                  |
| Encrypted reasoning tokens  | ✅ GA       | Persists reasoning context across turns (Responses API only).                                                 |
| Optimized token caching     | ✅ GA       | Saves ≈ 50 – 75 % tokens on tuned models.                                                                     |
| Web search tool             | ✅ GA       | Exposed as a tool so the model chooses when to search, or toggle manually with `web_search_toggle_filter.py`. |
| Image generation            | ⚠️ Planned | Coming soon.                                                                                                  |
| Image input (vision)        | ⚠️ Planned | Vision support slated for a future release.                                                                   |
| File upload                 | ⚠️ Planned | Upload & parse files in the pipeline roadmap.                                                                 |

### Other Quality of Life Improvements

* **Pseudo-models**:

  * `o3-mini-high`: Alias for `o3-mini` with enforced high reasoning effort.
  * `o4-mini-high`: Alias for `o4-mini` with enforced high reasoning effort.

* **Debug Logging**:

  * When `LOG_LEVEL` is set to `debug`, detailed logs are emitted as in‑message citations.
  * Set globally at pipe level or per user via user valve (`user` valve overrides global setting).

### Tested Models

All models that support the responses API should work.  Below are the models that have been tested:

| Model ID          | Status | Notes                                              |
| ----------------- | ------ | -------------------------------------------------- |
| chatgpt-4o-latest | ✅      | Fully compatible.                                  |
| codex-mini-latest | ✅      | Fully compatible.                                  |
| gpt-4.1           | ✅      | Fully compatible.                                  |
| gpt-4o            | ✅      | Fully compatible.                                  |
| o3                | ✅      | Fully compatible.                                  |
---

# Documentation

## Valves

Adjust pipeline behavior using the following common valves:

| Valve                        | Description                                                |
| ---------------------------- | ---------------------------------------------------------- |
| `API_KEY`                    | Your OpenAI API key.                                       |
| `BASE_URL`                   | OpenAI API base URL.                                       |
| `MODEL_ID`                   | Comma-separated list of model identifiers.                 |
| `ENABLE_WEB_SEARCH`          | Toggle the built-in web search tool.                       |
| `ENABLE_IMAGE_GENERATION`    | Enable experimental image generation.                      |
| `ENABLE_NATIVE_TOOL_CALLING` | Activate OpenAI's native function calling.                 |
| `ENABLE_REASON_SUMMARY`      | Provide concise summaries of model reasoning.              |
| `LOG_LEVEL`                  | Control log verbosity per message (`debug`, `info`, etc.). |

> For additional valves and default configurations, refer to the source file.

## Core Concepts

* **Responses API Endpoint** – Uses OpenAI's advanced Responses API (instead of the classic completions API), enabling richer features such as native tool calling and reasoning traces.
* **Valves Configuration** – Each setting is exposed through valves, allowing seamless adjustments without code changes.
* **History Reconstruction** – Previous tool responses are replayed when creating new requests, ensuring continuity.
* **Persistent Tool Results** – Tool outputs are preserved alongside messages, making them readily available in subsequent interactions.
* **Encrypted Reasoning Tokens** – Specialized reasoning tokens (`encrypted_content`) are stored to optimize future queries and follow-ups.

---

## Persist OpenAI Response Items

Non-message items returned from the Responses API (e.g., function calls, encrypted reasoning tokens, etc..) are stored in the chat record under a custom `openai_responses_pipe` property. This enables the pipe to accurately reconstruct the full context history, including tool outputs and reasoning data.

This design is important for two key reasons:

1. **Improved caching and cost efficiency**: By precisely reconstructing the original message context, we maximize cache hits and can take advantage of OpenAI's cache-based pricing (up to 75% discount!).
2. **Better performance and faster responses**: Including elements like encrypted reasoning tokens prevents the model from having to start from scratch and re-reason previous steps, resulting in faster and more efficient responses.

You can inspect this data structure by opening **Developer Tools** in Edge or Chrome and navigating to **Network**. Look for the POST request to the specific chat endpoint (e.g., `https://localhost:8080/api/v1/chats/<chat_id>`) and check the **Preview** tab.

Full Chat JSON Structure Example:

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
        // Flattened version of messages (similar shape as above)
      }
    ],
    "tags": ["<optional_tag>", "..."],
    "timestamp": <unix_ms>,
    "files": [
      // Any attached files
    ],

    // ─── Custom Extension: Added by openai_responses_pipe ───────────────
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
    // ────────────────────────────────────────────────────────────────────
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
   During replay or follow-up turns, the pipe can precisely rebuild the state of the conversation, including tools or reasoning results not visible in plain messages.
2. **Model-Specific Binding**
   Some items (especially \*\*encrypted reasoning tokens!) \*\*can only be used with the exact model that produced them. Injecting these into a different model’s context may result in **errors** or degraded performance. Binding items to the generating model avoids this.

By storing raw `items` exactly as received from the API, the system remains forward-compatible with future changes to the Responses API structure.
