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
| Response item persistence | ✅ GA | 2025-06-11 | Stores function calls and other non-message items using invisible IDs in empty links. |
| Truncation control | ✅ GA | 2025-06-10 | Valve `TRUNCATION` sets the responses `truncation` parameter (auto or disabled). Works with per-model `max_completion_tokens`. |
| Custom parameter pass-through | ✅ GA | 2025-06-14 | Use Open WebUI's custom parameters to set additional OpenAI fields. `max_tokens` is automatically mapped to `max_output_tokens`. |
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
- **Custom parameters**: Pass extra OpenAI settings via Open WebUI's "Custom Parameters" feature. `max_tokens` becomes `max_output_tokens` automatically.

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
By default, Open WebUI only stores the assistant’s final response and discards all intermediate response items. Instead, persisting **all** response items (in their original order):

* Significantly reduces latency by eliminating redundant tool calls and reasoning re-generation (especially noticeable with o-series models).
* Reduces cost through improved OpenAI cache hits (saving approximately 50–75% on input tokens).

**And thus, the core challenge...**

How do we store these response elements without revealing them to the end-user and still ensure compatibility with Open WebUI's extensible filter pipeline?

### Specific Constraints
1. **Invisibility:**
   * All non-message items must remain hidden from the user. Only visible assistant messages should appear in the interface.
2. **Accurate Ordering:**
   * Response items must be persisted precisely in the order produced by the model, supporting complex interactions (e.g., assistant messages interleaved with tool calls, reasoning steps, and back to assistant messages within a single response).
3. **Compatibility with Open WebUI Filter Pipeline:**
   * Context must be reconstructed exclusively from the `body["messages"]` structure provided by Open WebUI after all pipeline filters have applied their modifications:

Constraint #3 is particularly challenging since `body["messages"]` only includes two fields: `role` and `content` and doesn't support additional metadata / properties.

```python
body = {
  "messages": [
    { "role": "system", "content": "System prompt text..." },
    { "role": "user", "content": "User question..." }
  ]
}
```

### Optimal Solution: Invisible Metadata Encoding
To address these challenges effectively, we embed short, invisible metadata references (unique IDs) directly within `body["messages"]["content"]` using **empty Markdown links**. The full, unmodified OpenAI response JSON is persisted separately via `Chats.update_chat_by_id()`.

For example, an assistant message visibly appears as:
```python
body["messages"] = { "role": "assistant", "content": "[](id1)[](id2)The result of \\( 34234 \\times \\pi \\) is approximately 107,549.28." }
```
Here, the hidden identifier is embedded invisibly via an empty link after the message content.

An empty link (`[](secret)`) stays invisible even if rendered on its own line. For example:

```
yield "\n[](topSecret1)\n# test"
```
won't disrupt the Markdown heading that follows.

On subsequent API calls:

1. The pipeline decodes the hidden identifiers embedded in the empty links.
2. Using these identifiers, it retrieves the corresponding complete metadata from the database.
3. The pipeline reconstructs the original conversation accurately, preserving the precise ordering and context generated by the model.

_**Why encode identifiers and not the entire metadata directly?**_
If the entire JSON response were embedded in the message, it would be copied to the clipboard along with the visible text. Using a compact UID keeps the message clean while still letting the backend look up the full metadata.

### Practical Example: Embedding OpenAI Function Calls into Assistant Responses

This example demonstrates how the manifold seamlessly embeds hidden metadata IDs directly into assistant responses, preserving **exact OpenAI response items** to ensure accurate context reconstruction.

---

#### 1️⃣ User asks a question:

```json
{
  "role": "user",
  "content": "Calculate 34234 multiplied by pi."
}
```

---

#### 2️⃣ OpenAI initiates a function call:

OpenAI responds with a `function_call` event to invoke a calculator tool:

```json
{
  "type": "function_call",
  "id": "fc_684a191491048192a17c7b648432dbf30c824fb282e7959d",
  "call_id": "call_040gVKjMoMqU34KOKPZZPwql",
  "name": "calculator",
  "arguments": "{\"expression\":\"34234*pi\"}",
  "status": "completed"
}
```

* We persist to the DB in a special schema we define.  `01HX4Y2VW5VR2Z2HDQ5QY9REHB` is the unique id we generate. 

```json
"01HX4Y2VW5VR2Z2HDQ5QY9REHB": {
  "model": "gpt-4o",
  "created_at": 1718073601,
  "payload": {
    "type": "function_call",
    "id": "fc_684a191491048192a17c7b648432dbf30c824fb282e7959d",
    "call_id": "call_040gVKjMoMqU34KOKPZZPwql",
    "name": "calculator",
    "arguments": "{\"expression\":\"34234*pi\"}",
    "status": "completed"
  },
  "message_id": "msg_9fz4qx7e"
}
```

* We immediately insert `[](01HX4Y2VW5VR2Z2HDQ5QY9REHB)` and yield it so the ID is permanently embedded into `body["messages"]["content"]`.

---

#### 3️⃣ Tool returns the function call output:

Gather tool result, persist to DB and yield encoded invisible ID (similar to previous step)

---

#### 4️⃣ Assistant provides the visible response:

Finally, the assistant sends the human-readable message:

```
"34234 multiplied by π equals approximately 107549.28."
```

* We stream (yield) it.

---

#### 📌 **Final Stream (Invisible IDs + Response)**:

```
[](01HX4Y2VW5VR2Z2HDQ5QY9REHB)[](01HX4Y2VW6B091XE84F5G0Z8NF)The result of \\( 34234 \\times \\pi \\) is approximately 107,549.28.
```

*(Invisible IDs precede the visible text in this example however OpenAI can have additional tool calls / reasonsing at any point.)*

---

#### 📦 **Final Chat DB Record**:

```json
{
  "id": "61fba20f-2395-40f8-917f-6f80036a5fe9",
  "user_id": "91216674-177d-4d5b-8a0b-a2d83783eb54",
  "title": "New Chat",
  "chat": {
    "id": "",
    "title": "New Chat",
    "models": ["openai_responses.gpt-4o"],
    "history": {
      "messages": {
        "933ea7dc-d9aa-4981-a447-b06846376136": {
          "id": "933ea7dc-d9aa-4981-a447-b06846376136",
          "parentId": null,
          "childrenIds": ["9ce5b52c-189b-4cbf-a5f3-421d6cef79b1"],
          "role": "user",
          "content": "what is 34234*pi",
          "timestamp": 1749686545,
          "models": ["openai_responses.gpt-4o"]
        },
        "9ce5b52c-189b-4cbf-a5f3-421d6cef79b1": {
          "id": "9ce5b52c-189b-4cbf-a5f3-421d6cef79b1",
          "parentId": "933ea7dc-d9aa-4981-a447-b06846376136",
          "childrenIds": [],
          "role": "assistant",
          "content": "[](01HX4Y2VW5VR2Z2HDQ5QY9REHB)[](01HX4Y2VW6B091XE84F5G0Z8NF)The result of \\( 34234 \\times \\pi \\) is approximately 107,549.28."
          "model": "openai_responses.gpt-4o",
          "modelName": "OpenAI: GPT-4o ★★☆☆",
          "timestamp": 1749686545,
          "statusHistory": [
            {
              "description": "🛠️ Let me try calculator…",
              "done": false,
              "hidden": false
            },
            {
              "description": "🛠️ Done—the tool finished!",
              "done": true,
              "hidden": false
            }
          ],
          "usage": {
            "input_tokens": 1657,
            "output_tokens": 41,
            "total_tokens": 1698,
            "turn_count": 2,
            "function_call_count": 1
          },
          "done": true
        }
      },
      "currentId": "9ce5b52c-189b-4cbf-a5f3-421d6cef79b1"
    },
    "openai_responses_pipe": {
      "__v": 3,
      "items": {
        "01HX4Y2VW5VR2Z2HDQ5QY9REHB": {
          "model": "gpt-4o",
          "created_at": 1749686551,
          "payload": {
            "type": "function_call",
            "id": "fc_684a191491048192a17c7b648432dbf30c824fb282e7959d",
            "call_id": "call_040gVKjMoMqU34KOKPZZPwql",
            "name": "calculator",
            "arguments": "{\"expression\":\"34234*pi\"}",
            "status": "completed"
          },
          "message_id": "9ce5b52c-189b-4cbf-a5f3-421d6cef79b1"
        },
        "01HX4Y2VW6B091XE84F5G0Z8NF": {
          "model": "gpt-4o",
          "created_at": 1749686552,
          "payload": {
            "type": "function_call_output",
            "call_id": "call_040gVKjMoMqU34KOKPZZPwql",
            "output": "34234*pi = 107549.282902993"
          },
          "message_id": "9ce5b52c-189b-4cbf-a5f3-421d6cef79b1"
        }
      },
      "messages_index": {
        "9ce5b52c-189b-4cbf-a5f3-421d6cef79b1": {
          "role": "assistant",
          "done": true,
          "item_ids": [
            "01HX4Y2VW5VR2Z2HDQ5QY9REHB",
            "01HX4Y2VW6B091XE84F5G0Z8NF"
          ]
        }
      }
    },
    "timestamp": 1749686545104
  },
  "updated_at": 1749686551,
  "created_at": 1749686545,
  "share_id": null,
  "archived": false,
  "pinned": false,
  "meta": {},
  "folder_id": null
}
```

**Pro Tip**
You can inspect the DB chat item directly in your browser by opening **Developer Tools** and examining the POST request for a chat in the **Network** tab.
