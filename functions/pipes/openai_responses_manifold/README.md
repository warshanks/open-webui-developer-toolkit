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

---

# The Magic Behind this Pipe
### Persisting Non-Message Items (function_call, function_call_results, reasoning tokens, etc..)

The OpenAI Responses API returns essential non-message components (such as reasoning tokens, function calls, and tool outputs). These response items are produced sequentially, reflecting the model’s internal decision-making process.

**For example:**

```json
[
  {
    "id": "rs_6849f90497fc8192a013fb54f888948c0b902dab32480d90",
    "type": "reasoning",
    "encrypted_content": "[ENCRYPTED_TOKENS_HERE]"
  },
  {
    "type": "function_call",
    "function_call": {
      "name": "get_weather",
      "arguments": {
        "location": "New York"
      }
    }
  },
  {
    "type": "function_call_result",
    "function_result": {
      "location": "New York",
      "temperature": "72°F",
      "condition": "Sunny"
    }
  },
  {
    "type": "message",
    "role": "assistant",
    "content": "It’s currently 72°F and sunny in New York."
  }
]
```

Storing only the final assistant message discards the context that produced it. Appending all response items (in the order they were produced) ensures:

* **Accurately reconstructing the exact conversation context** from previous interactions.
* **Reducing latency significantly** by avoiding redundant reasoning regeneration.
* ****Reduces cost** by improving OpenAI cache hit's** which would otherwise have missed (saving up to 50–75% $$).


#### The Core Challenge
**How do we store these necessary response elements without revealing them to the end-user and still ensure compatibility with Open WebUI's extensible filter pipeline?**

### Specific Constraints
1. **Invisibility:**
   * All non-message items must remain hidden from the user. Only visible assistant messages should appear in the interface.
2. **Accurate Ordering:**
   * Response items must be persisted precisely in the order produced by the model, supporting complex interactions (e.g., assistant messages interleaved with tool calls, reasoning steps, and back to assistant messages within a single response).
3. **Compatibility with Open WebUI Filter Pipeline:**
   * Context must be reconstructed exclusively from the `body["messages"]` structure provided by Open WebUI after all pipeline filters have applied their modifications:
   * 
```json
body = {
  "messages": [
    { "role": "system", "content": "System prompt text..." },
    { "role": "user", "content": "User question..." }
  ]
}
```

This structure only includes two fields: `role` and `content`. There is no provision for additional metadata or chat identifiers directly in the request, complicating the linkage to stored metadata.

### Optimal Solution: Invisible Metadata Encoding
To address these challenges effectively, the chosen solution involves encoding short, invisible metadata references directly within the message content using zero-width characters:

* **Invisible Encoding:** Metadata references (short unique IDs) are embedded invisibly into the assistant’s message content.
* **Separate Comprehensive Storage:** The full, unmodified OpenAI response JSON is stored separately via `Chats.update_chat_by_id()`.

For example, an assistant message visibly appears as:
```json
{ "role": "assistant", "content": "It’s currently 72°F and sunny in New York.\u200b\u200b\u200b\u200b" }
```
Here, the hidden zero-width encoded identifier (\u200b) is embedded invisibly after the message content.

_**Why encode identifiers and not the entire metadata directly?**_
Embedding full OpenAI response metadata directly into zero-width characters significantly increases storage overhead. Instead, encoding a concise, unique identifier optimizes storage while enabling complete metadata retrieval from the database.

### Reconstruction Workflow

On subsequent API calls:

1. The pipeline decodes the hidden zero-width encoded identifiers embedded in the messages.
2. Using these identifiers, it retrieves the corresponding complete metadata from the database.
3. The pipeline reconstructs the original conversation accurately, preserving the precise ordering and context generated by the model.

### Practical Example

Stored comprehensive metadata (in the database):

```json
"openai_responses_pipe": {
  "__v": 2,
  "messages": {
    "<message_id>": {
      "model": "gpt-4o",
      "created_at": 1718073600,
      "items": [
        { "type": "reasoning", "encrypted_content": "[ENCRYPTED_REASONING_TOKENS]" },
        { "type": "function_call", "function_call": { "name": "get_weather", "arguments": { "location": "New York" } } },
        { "type": "function_call_result", "function_result": { "location": "New York", "temperature": "72°F", "condition": "Sunny" } },
        { "type": "message", "role": "assistant", "content": "It’s currently 72°F and sunny in New York." }
      ]
    }
  }
}
```












**Pro Tip**
You can inspect the DB chat item directly in your browser by opening **Developer Tools** and examining the POST request for a chat in the **Network** tab.

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
