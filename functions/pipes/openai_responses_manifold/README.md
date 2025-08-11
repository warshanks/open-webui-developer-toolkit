# OpenAI Responses Manifold
**Enables advanced OpenAI features (function calling, web search, visible reasoning summaries, and more) directly in [Open WebUI](https://github.com/open-webui/open-webui).**

🆕 Now supports OpenAI's GPT-5 model family in the API — [`Learn more about GPT-5 support`](#-gpt-5-model-support-api--manifold).

## Setup Instructions
1. Navigate to **Open WebUI ▸ Admin Panel ▸ Functions** and press **Import from Link**
   <img width="894" alt="image" src="https://github.com/user-attachments/assets/4a5a0355-e0af-4fb8-833e-7d3dfb7f10e3" />
2. Paste one of the following links:

| Branch                 | Description                                                              | Link                                                                                                                                       |
|------------------------|---------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| **Main** (recommended) | Stable production version. Receives regular, tested updates.              | `https://github.com/jrkropp/open-webui-developer-toolkit/blob/main/functions/pipes/openai_responses_manifold/openai_responses_manifold.py` |
| **Alpha Preview**      | Pre-release version with early features (2–4 weeks ahead of main).        | `https://github.com/jrkropp/open-webui-developer-toolkit/blob/alpha-preview/functions/pipes/openai_responses_manifold/openai_responses_manifold.py` |

3. **⚠️ The Function ID MUST be set to `openai_responses`**, as it is currently hardcoded throughout the pipe.  This requirement will be removed in a future release.
<img width="1252" alt="image" src="https://github.com/user-attachments/assets/ffd3dd72-cf39-43fa-be36-56c6ac41477d" />
4. You are done!

---

## Features

| Feature | Status | Last updated | Notes |
| --- | --- | --- | --- |
| Native function calling | ✅ GA | 2025-06-04 | Automatically enabled for supported models. |
| Visible reasoning summaries | ✅ GA | 2025-08-07 | Available for o‑series models only. Requires `reasoning` parameter. |
| Encrypted reasoning tokens | ✅ GA | 2025-08-07 | Persists reasoning context across turns. Requires `reasoning` parameter. |
| Optimized token caching | ✅ GA | 2025-06-03 | Save up to ~50–75 % on supported models. |
| Web search tool | ✅ GA | 2025-06-03 | Automatically invoked or toggled manually. |
| Task model support | ✅ GA | 2025-08-07 | Use model as [Open WebUI External Task Model](https://docs.openwebui.com/tutorials/tips/improve-performance-local/) (title generation, tag generation, etc.). `gpt-5-mini-minimal` is recommended as a hidden task model. |
| Streaming responses (SSE) | ✅ GA | 2025-06-04 | Real-time, partial output streaming for text and tool events. |
| Usage Pass-through | ✅ GA | 2025-06-04 | Tokens and usage aggregated and passed through to Open WebUI GUI. |
| Response item persistence | ✅ GA | 2025-06-27 | Persists items via newline-wrapped comment markers (v2) that embed type, 16-character ULIDs and metadata. |
| Open WebUI Notes compatibility | ✅ GA | 2025-07-14 | Works with ephemeral Notes that omit `chat_id`. |
| Expandable status output | ✅ GA | 2025-07-01 | Progress steps rendered via `<details>` tags. Use `ExpandableStatusEmitter` to add entries. |
| Inline citation events | ✅ GA | 2025-07-28 | Valve `CITATION_STYLE` controls `[n]` vs source name. |
| Truncation control | ✅ GA | 2025-06-10 | Valve `TRUNCATION` sets the responses `truncation` parameter (auto or disabled). Works with per-model `max_completion_tokens`. |
| Custom parameter pass-through | ✅ GA | 2025-06-14 | Use Open WebUI's custom parameters to set additional OpenAI fields. `max_tokens` is automatically mapped to `max_output_tokens`. |
| Deep Search Support | 🔄 In-progress | 2025-06-29 | Add support for o3-deep-research, o4-mini-deep-research. |
| Image input (vision) | 🔄 In-progress | 2025-06-03 | Pending future release. |
| Image generation tool | 🕒 Backlog | 2025-06-03 | Incl. multi-turn image editing (e.g., upload and modify). |
| File upload / file search tool | 🕒 Backlog | 2025-06-03 | Roadmap item. |
| Code interpreter tool | 🕒 Backlog | 2025-06-03 | [OpenAI docs](https://platform.openai.com/docs/guides/tools-code-interpreter) |
| Computer use tool | 🕒 Backlog | 2025-06-03 | [OpenAI docs](https://platform.openai.com/docs/guides/tools-computer-use) |
| Live conversational voice (Talk) | 🕒 Backlog | 2025-06-03 | Requires backend patching; design under consideration. |
| Dynamic chat titles | 🕒 Backlog | 2025-06-03 | For progress/status indication during long tasks. |
| MCP tool support | 🔄 In-progress | 2025-06-23 | Attach remote MCP servers via the `REMOTE_MCP_SERVERS_JSON` valve. |

### Other Features

* **Pseudo-model aliases**
  You can list `o3-mini-high`, `o4-mini-high`, `gpt-5-high`, `gpt-5-thinking`, `gpt-5-minimal`, `gpt-5-mini-minimal`, and `gpt-5-nano-minimal` in the `MODELS` valve just like regular models.
  These are **virtual aliases** (not real OpenAI models) that automatically map to the underlying model and set `reasoning_effort` to `"high"` or `"minimal"` as indicated.
  For example, `gpt-5-thinking` uses `gpt-5` with `reasoning_effort="high"`, while the `*-minimal` variants run with minimal reasoning and are handy for task models like a hidden `gpt-5-mini-minimal`.

* **Debug logging**
  Set `LOG_LEVEL` to `debug` to include inline debug logs inside assistant messages.
  Can be configured **globally** via the pipe valve OR **per user** via user valve.

* **Expandable status blocks**
  Tool progress is shown using `<details type="openai_responses.expandable_status">` blocks.
  The `ExpandableStatusEmitter` helper simplifies adding new steps programmatically.

* **Truncation strategy**
  Use the `TRUNCATION` valve to control how long prompts are handled:

  * `auto` (default): removes middle context if the request exceeds token limits
  * `disabled`: returns a 400 error if the context is too long
    This works alongside per-model `max_completion_tokens` constraints.

* **Custom parameter support**
  Pass OpenAI-compatible fields via Open WebUI's **Custom Parameters**.
  For convenience, `max_tokens` is automatically translated to `max_output_tokens`.

* **Remote MCP server integration** (experimental)
  Set the `REMOTE_MCP_SERVERS_JSON` valve to a JSON object or array describing [Remote MCP](https://platform.openai.com/docs/guides/tools-remote-mcp) servers.
  These are appended to each request’s `tools` list before being sent to OpenAI.
  Supports options like `require_approval` and automatic tool caching.

### Tested models
The manifold should work with any model that supports the responses API. Confirmed with:

* **GPT‑5 family** – `gpt-5`, `gpt-5-mini`, and `gpt-5-nano` are reasoning models. The non‑reasoning ChatGPT model is available as `gpt-5-chat-latest`. Pseudo‑model IDs like `gpt-5-high`, `gpt-5-thinking`, and the `*-minimal` variants are also recognized.

| Model ID | Status |
| --- | --- |
| gpt-5 | ✅ |
| gpt-5-mini | ✅ |
| gpt-5-nano | ✅ |
| gpt-5-chat-latest | ✅ |
| chatgpt-4o-latest | ✅ |
| codex-mini-latest | ✅ |
| gpt-4.1 | ✅ |
| gpt-4o | ✅ |
| o3 | ✅ |
| o3-pro | ✅ |
| o3-deep-research | ❌ |
| o4-mini-deep-research | ❌ |

---

# 🧠 GPT-5 Model Support (API + Manifold)

The Responses Manifold supports the current **GPT-5 family** exposed in the API:

- `gpt-5` *(reasoning model)*
- `gpt-5-mini` *(reasoning model)*
- `gpt-5-nano` *(reasoning model)*
- `gpt-5-chat-latest` *(non-reasoning ChatGPT variant)*

### Key behavior (practical notes)

- **All `gpt-5`, `gpt-5-mini`, and `gpt-5-nano` are reasoning models.** Setting `reasoning_effort="minimal"` reduces thinking but does **not** make them non-reasoning. For a non-reasoning chat model, use **`gpt-5-chat-latest`**. ([OpenAI][1])
- **Tool calling limitation:** `gpt-5-chat-latest` does not currently support native tool calling (e.g., function calls or web search). This is the primary limitation compared to reasoning models. We expect that a future gpt-5-main high-throughput API model may support tools while keeping the non-reasoning behavior.
- **Latency:** Even with `minimal`, GPT-5 models may still "think." For ultra-low latency tasks (e.g., Open WebUI Task Models), consider `gpt-4.1-nano` until OpenAI ships a lower-latency v5 task model.  
- **Output style:** `gpt-5-chat-latest` is tuned for polished, end-user-friendly chat and usually needs little to no system prompt. The reasoning models (`gpt-5*`) benefit from a brief style system prompt (e.g., "respond in concise Markdown with headings and lists"). See [system_prompts/](./system_prompts/) for examples.

### GPT-5 in ChatGPT vs the API (and our future router)

**In ChatGPT,** "GPT-5" isn’t a single model — it’s a **mix** of reasoning, minimal-reasoning, and non-reasoning variants chosen automatically by a **model router** that balances speed, difficulty, tools, and intent. [More →][1]

**In the API,** you pick specific models directly:
- `gpt-5`, `gpt-5-mini`, `gpt-5-nano` — reasoning enabled by default.  
- `reasoning_effort="minimal"` reduces thinking but is **not** the same as the non-reasoning ChatGPT model.  
- The **non-reasoning** ChatGPT variant is exposed separately as **`gpt-5-chat-latest`**.

> **Planned:** We may add a built-in **`gpt-5-router`** pseudo model ID to mimic ChatGPT’s behavior: it would inspect users request (latency tolerance, tool usage, length/complexity, "think hard" cues, etc...) and route to an ideal target (e.g., `gpt-5-chat-latest` for quick tasks, `gpt-5` for reasoning, etc...).

### Pseudo IDs → API Mappings *(subject to change)*

This manifold also exposes pseudo **aliases** that map to real API models with preset `reasoning_effort`. If an effort suffix is omitted, the API default (medium) applies.

| Pseudo ID                           | Maps to                                     | Notes                                                                  |
| ----------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `gpt-5-thinking`                    | `gpt-5`                                     | Default (medium) reasoning; mirrors "thinking".                        |
| `gpt-5-thinking-minimal`            | `gpt-5` + `reasoning_effort="minimal"`      | Fastest `gpt-5` while still a reasoning model. ([OpenAI][1])           |
| `gpt-5-thinking-high`               | `gpt-5` + `reasoning_effort="high"`         | Maximum test-time reasoning. ([OpenAI][1])                              |
| `gpt-5-thinking-mini`               | `gpt-5-mini`                                | Default (medium) reasoning.                                            |
| `gpt-5-thinking-mini-minimal`       | `gpt-5-mini` + `reasoning_effort="minimal"` | Budget/latency-tilted background tasks. ([OpenAI][1])                  |
| `gpt-5-thinking-nano`               | `gpt-5-nano`                                | Default (medium) reasoning.                                            |
| `gpt-5-thinking-nano-minimal`       | `gpt-5-nano` + `reasoning_effort="minimal"` | Cheapest option with minimal reasoning. ([OpenAI][1])                  |
| `gpt-5-main` *(not available)*      | *not exposed via API yet*                   | Reserved for high-throughput "main". Disabled until an API model exists. |
| `gpt-5-main-mini` *(not available)* | *not exposed via API yet*                   | Appears in the system card for ChatGPT routing; we don’t alias this.   |
| `gpt-5-thinking-pro` *(not available)* | *not exposed via API yet*                | ChatGPT-only "parallel test-time compute" setting. ([System card][2])  |

> **What is `gpt-5-main`?**  
> In OpenAI’s system card, gpt-5-main refers to a high-throughput, non-reasoning model family. At present, the API only exposes the thinking models (gpt-5, gpt-5-mini, gpt-5-nano) plus the non-reasoning ChatGPT variant gpt-5-chat-latest. There is no API equivalent of the high-throughput "main" model. Until OpenAI ships a true API main model (or adds a parameter to switch between reasoning and high-throughput modes), gpt-5-main remains reserved to avoid confusion. See [OpenAI][1] and the [system card][2].

> **Disclaimer:** This reflects what we’ve verified from OpenAI’s launch materials and the GPT-5 system card as of **Aug 11, 2025** and may change without notice. We’ll update this section as OpenAI updates docs or behavior.

[1]: https://openai.com/index/introducing-gpt-5-for-developers/ "Introducing GPT-5 for developers | OpenAI"  
[2]: https://cdn.openai.com/pdf/8124a3ce-ab78-4f06-96eb-49ea29ffb52f/gpt5-system-card-aug7.pdf "GPT-5 System Card (Aug 7, 2025)"

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
By default, Open WebUI only stores the assistant’s final response and discards all intermediate response items. Instead, if we persist **all** response items (in their original order) it...

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

Constraint #3 is particularly challenging since `body["messages"]` only includes two fields: `role` and `content` and doesn't support additional metadata / properties.  We must somehow store the non-visible items inside `body["messages"]["contents"]`

```python
body = {
  "messages": [
    { "role": "system", "content": "System prompt text..." },
    { "role": "user", "content": "User question..." }
  ]
}
```

### Invisible Marker Strategy (v2):
Open WebUI ignores content enclosed within markdown comments (`[hidden comment]: #`), making them ideal for embedding hidden metadata directly into assistant responses. We can use these hidden markdown comments to store references (unique IDs) to response items we've saved elsewhere. [Learn more about markdown comments →](https://www.markdownguide.org/hacks/#comments)

Here's how it works:

1. **Persist Response Items:**
   We store the complete OpenAI response items using Open WebUI’s built-in method, `Chats.update_chat_by_id()`. Each item receives a unique 16-character identifier:

   ```json
   "01HX4Y2VW5VR2Z2H": {
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

2. **Embed Invisible Markers:**
  We yield these IDs as invisible markdown link, e.g.,

  ```text
  [openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H]: #
  ```
  so they are permanently embedded in `body["messages"]["content"]`.

3. **Reconstruct Message History:**
   Later, the manifold detects these invisible comment markers, retrieves the associated stored response items, and accurately reconstructs the full message history—including all hidden intermediate responses—in their original order.

#### Marker Specification
For future extensibility, each invisible comment marker adheres to this structured format:

```
\n[openai_responses:v2:<item_type>:<id>[?model=<model_id>&key=value...]]: #\n
```

* `<item_type>` – The exact OpenAI event type (`function_call`, `reasoning`, etc.).
* `<id>` – A unique 16-character ID used as the database key.
* Optional metadata via query parameters (e.g., the originating model ID under `model`).

Markers are enclosed within markdown comment syntax (`[comment]: # (comment content)`) and surrounded by line breaks (`\n`) to ensure invisibility without disrupting markdown formatting or content flow.

_**Why not embed the entire JSON?**_
Embedding only a marker avoids leaking large payloads into the clipboard while still giving the backend enough information to find the stored data.

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

* We persist the payload in the chat db using a unquie identifier.

```json
"01HX4Y2VW5VR2Z2H": {
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

* We immediately yield `[openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H] #` so the marker is permanently embedded into `body["messages"]["content"]`.

---

#### 3️⃣ Tool returns the function call output:

Gather tool result, persist to DB and yield another invisible marker (similar to previous step)

---

#### 4️⃣ Assistant provides the visible response:

Finally, the assistant sends the human-readable message:

```
"34234 multiplied by π equals approximately 107549.28."
```

* We stream (yield) it.

---

#### 📌 **Final Stream (Invisible markers + Response)**:

```

[openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H?model=openai_responses.gpt-4o]: #

[openai_responses:v2:function_call_output:01HX4Y2VW6B091XE?model=openai_responses.gpt-4o]: #

The result of \(34234 \times \pi\) is approximately 107,549.28.
```

*(Invisible markers precede the visible text in this example however OpenAI can have additional tool calls or reasoning at any point.)*

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
          "content": "[openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H?model=openai_responses.gpt-4o]: #\n[openai_responses:v2:function_call_output:01HX4Y2VW6B091XE?model=openai_responses.gpt-4o]: #\nThe result of \\(34234 \\times \\pi\\) is approximately 107,549.28."
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
        "01HX4Y2VW5VR2Z2H": {
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
        "01HX4Y2VW6B091XE": {
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
            "01HX4Y2VW5VR2Z2H",
            "01HX4Y2VW6B091XE"
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
