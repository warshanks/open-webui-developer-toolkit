# OpenAI Responses Manifold

Enables advanced OpenAI features (function calling, web search, visible reasoning summaries, and more) directly in [Open WebUI](https://github.com/open-webui/open-webui).

Now supports OpenAI’s GPT‑5 family in the API — [Learn more](#gpt-5-model-support).

## Contents

* [Setup](#setup)
* [Features](#features)
* [Advanced Features](#advanced-features)
* [Tested Models](#tested-models)
* [GPT‑5 Model Support](#gpt-5-model-support)
* [How It Works (Design Notes)](#how-it-works-design-notes)
* [Troubleshooting / FAQ](#troubleshooting--faq)

## Setup

1. In **Open WebUI ▸ Admin Panel ▸ Functions**, click **Import from Link**.
   
   <img width="450" alt="image" src="https://github.com/user-attachments/assets/4a5a0355-e0af-4fb8-833e-7d3dfb7f10e3" />

2. Paste one of the following links, depending on which version you want:

   * **Main** (recommended) – Stable production build with regular, tested updates:

     ```
     https://github.com/jrkropp/open-webui-developer-toolkit/blob/main/functions/pipes/openai_responses_manifold/openai_responses_manifold.py
     ```

   * **Alpha Preview** – Pre-release build with early features, typically 2–4 weeks ahead of main:

     ```
     https://github.com/jrkropp/open-webui-developer-toolkit/blob/alpha-preview/functions/pipes/openai_responses_manifold/openai_responses_manifold.py
     ```

3. **⚠️ Important: Set the Function ID to `openai_responses`.**
   
   This value is currently hardcoded in the pipe and must match exactly. It will become configurable in a future release.
   
   <img width="800" alt="image" src="https://github.com/user-attachments/assets/ffd3dd72-cf39-43fa-be36-56c6ac41477d" />

4. Done! 🎉

## Features

| Feature                        | Status         | Last updated | Notes                                                                                                                                              |
| ------------------------------ | -------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Native function calling        | ✅ GA           | 2025‑06‑04   | Auto‑enabled on supported models.                                                                                                                  |
| Visible reasoning summaries    | ✅ GA           | 2025‑08‑07   | o‑series only; requires `reasoning`.                                                                                                               |
| Encrypted reasoning tokens     | ✅ GA           | 2025‑08‑07   | Persists reasoning context across turns; requires `reasoning`.                                                                                     |
| Optimized token caching        | ✅ GA           | 2025‑06‑03   | Save \~50–75% on supported models.                                                                                                                 |
| Web search tool                | ✅ GA           | 2025‑06‑03   | Auto‑invoked or manual toggle.                                                                                                                     |
| Task model support             | ✅ GA           | 2025‑08‑07   | Use as an [External Task Model](https://docs.openwebui.com/tutorials/tips/improve-performance-local/). `gpt-4.1-nano` is a good hidden task model. |
| Streaming responses (SSE)      | ✅ GA           | 2025‑06‑04   | Real‑time text and tool events.                                                                                                                    |
| Usage pass‑through             | ✅ GA           | 2025‑06‑04   | Usage surfaced in Open WebUI.                                                                                                                      |
| Response item persistence      | ✅ GA           | 2025‑06‑27   | Persists items via v2 newline‑wrapped comment markers with 16‑char IDs.                                                                            |
| Open WebUI Notes compatibility | ✅ GA           | 2025‑07‑14   | Works with ephemeral Notes (no `chat_id`).                                                                                                         |
| Expandable status output       | ✅ GA           | 2025‑07‑01   | `<details>` blocks via `ExpandableStatusEmitter`.                                                                                                  |
| Inline citation events         | ✅ GA           | 2025‑07‑28   | Valve `CITATION_STYLE` controls `[n]` vs source name.                                                                                              |
| Truncation control             | ✅ GA           | 2025‑06‑10   | Valve `TRUNCATION`: `auto` or `disabled`. Honors per‑model `max_completion_tokens`.                                                                |
| Custom param pass‑through      | ✅ GA           | 2025‑06‑14   | Open WebUI Custom Parameters → OpenAI fields; `max_tokens` → `max_output_tokens`.                                                                  |
| Regenerate → `text.verbosity`  | ✅ GA           | 2025‑08‑11   | “Add Details”/“More Concise” map to `high`/`low` on GPT‑5 family.                                                                                  |
| Deep Search support            | 🔄 In progress | 2025‑06‑29   | o3‑deep‑research / o4‑mini‑deep‑research.                                                                                                          |
| Image input (vision)           | 🔄 In progress | 2025‑06‑03   | Pending release.                                                                                                                                   |
| Image generation tool          | 🕒 Backlog     | 2025‑06‑03   | Multi‑turn editing planned.                                                                                                                        |
| File upload / file search      | 🕒 Backlog     | 2025‑06‑03   | Roadmap item.                                                                                                                                      |
| Code interpreter               | 🕒 Backlog     | 2025‑06‑03   | See OpenAI docs.                                                                                                                                   |
| Computer use                   | 🕒 Backlog     | 2025‑06‑03   | See OpenAI docs.                                                                                                                                   |
| Live voice (Talk)              | 🕒 Backlog     | 2025‑06‑03   | Requires backend patching.                                                                                                                         |
| Dynamic chat titles            | 🕒 Backlog     | 2025‑06‑03   | Progress titles during long tasks.                                                                                                                 |
| MCP tool support               | 🔄 In progress | 2025‑06‑23   | Attach remote MCP via `REMOTE_MCP_SERVERS_JSON`.                                                                                                   |

## Advanced Features

* **Pseudo-model aliases**
  In the `MODELS` valve, you can include names like `o3-mini-high`, `o4-mini-high`, `gpt-5-high`, `gpt-5-thinking`, `gpt-5-minimal`, `gpt-5-mini-minimal`, and `gpt-5-nano-minimal`.
  These aliases map to actual models and set `reasoning_effort` to either `"high"` or `"minimal"`.
  Example: `gpt-5-thinking` → `gpt-5` with default (medium) reasoning.
  `*-minimal` variants lower test-time reasoning and are useful for hidden task models.

* **Debug logging**
  Set `LOG_LEVEL=debug` to embed inline debug logs in assistant messages. Can be applied globally (pipe valve) or per user (user valve).

* **Expandable status blocks**
  Tool progress can be shown using `<details type="openai_responses.expandable_status">`.
  Use `ExpandableStatusEmitter` to add steps programmatically.

* **Truncation strategy**
  The `TRUNCATION` valve supports:

  * `auto` (default): Removes middle context if limits are exceeded.
  * `disabled`: Returns a 400 error on overflow.
    Works with per-model `max_completion_tokens`.

* **Custom parameter support**
  “Custom Parameters” in Open WebUI map directly to OpenAI fields.
  For convenience, `max_tokens` is translated to `max_output_tokens`.

* **Regenerate → `text.verbosity`**
  When the last user input is “Add Details” or “More Concise”, sets `text.verbosity` to `high` or `low` (supported GPT-5 models only).

* **Remote MCP servers (experimental)**
  Set `REMOTE_MCP_SERVERS_JSON` to a JSON object or array describing [Remote MCP](https://platform.openai.com/docs/guides/tools-remote-mcp) servers.
  Appends these servers to each request’s `tools`. Supports `require_approval` and tool caching.

---

## Tested Models

The manifold targets any model that supports the Responses API. Confirmed with the official IDs below.

| Family               | **Official model ID**   | Type / modality                                               | Status | **Your notes**                                                           |
| -------------------- | ----------------------- | ------------------------------------------------------------- | :----: | ------------------------------------------------------------------------ |
| **GPT‑5**            | `gpt-5`                 | Reasoning                                                     |    ✅   |                                                                          |
|                      | `gpt-5-mini`            | Reasoning                                                     |    ✅   |                                                                          |
|                      | `gpt-5-nano`            | Reasoning                                                     |    ✅   |                                                                          |
|                      | `gpt-5-chat-latest`     | Chat‑tuned (non‑reasoning)                                    |    ✅   |  ([OpenAI Platform][1]) |
| **GPT‑4.1**          | `gpt-4.1`               | Non‑reasoning                                                 |    ✅   |                                                                          |
| **GPT‑4o**           | `gpt-4o`                | Text + image input → text output                              |    ✅   |                                                                          |
|                      | `chatgpt-4o-latest`     | Dynamic alias pointing to the GPT‑4o snapshot used in ChatGPT |    ✅   | Handy for parity checks; dynamic pointer. ([OpenAI Platform][2])         |
| **O‑series**         | `o3`                    | Reasoning                                                     |    ✅   |                                                                          |
|                      | `o3-pro`                | Reasoning (higher compute) — **Responses API only**           |    ✅   | ([OpenAI Platform][3])                                                   |
|                      | `o3-mini`               | Reasoning                                                     |    ✅   | Supported; lightweight O-series reasoning model. ([OpenAI Platform][11]) |
|                      | `o4-mini`               | Reasoning                                                     |    ✅   | Supported; cost-efficient O-series reasoning model. ([OpenAI][12])       |
| **Deep Research**    | `o3-deep-research`      | Agentic deep‑research model                                   |    ❌   | Not yet supported ([OpenAI Platform][4])                                 |
|                      | `o4-mini-deep-research` | Agentic deep‑research model                                   |    ❌   | Not yet supported ([OpenAI Platform][5])                                 |
| **Utility / Coding** | `codex-mini-latest`     | Lightweight coding/agent model                                |    ✅   | ([OpenAI Platform][6])                                                   |

### Pseudo‑model aliases (convenience IDs)

These **aliases** are supported by the pipe (via the `MODELS` valve). They resolve to official models and may set presets like `reasoning_effort` for you. *(Subject to change as OpenAI updates their platform.)* For GPT‑5 reasoning levels (minimal/low/medium/high), see OpenAI’s developer post. ([OpenAI][8])

| **Alias (you can use these in OpenAI Responses Manifold)**                        | **Resolves to (official ID)** | **Preset(s)**                | Suggested use                                                         |
| ------------------------------------------------------------------ | ----------------------------- | ---------------------------- | --------------------------------------------------------------------- |
| `gpt-5-auto`                                                       | `gpt-5-chat-latest`           | Router placeholder           | ChatGPT parity / quick smoke tests.                                   |
| `gpt-5-thinking`                                                   | `gpt-5`                       | Default (medium) reasoning   | General high‑quality prompts. ([OpenAI][8])                           |
| `gpt-5-minimal`, `gpt-5-thinking-minimal`                          | `gpt-5`                       | `reasoning_effort="minimal"` | Faster/cheaper while still reasoning. ([OpenAI][8])                   |
| `gpt-5-high`, `gpt-5-thinking-high`                                | `gpt-5`                       | `reasoning_effort="high"`    | Hard problems; max quality. ([OpenAI][8])                             |
| `gpt-5-thinking-mini`                                              | `gpt-5-mini`                  | Default (medium) reasoning   | Budget‑tilted tasks. ([OpenAI Platform][9])                           |
| `gpt-5-mini-minimal`, `gpt-5-thinking-mini-minimal`                | `gpt-5-mini`                  | `reasoning_effort="minimal"` | Hidden task model / latency‑sensitive. ([OpenAI Platform][9])         |
| `gpt-5-thinking-nano`                                              | `gpt-5-nano`                  | Default (medium) reasoning   | Very low cost; routing / triage. ([OpenAI Platform][10])              |
| `gpt-5-nano-minimal`, `gpt-5-thinking-nano-minimal`                | `gpt-5-nano`                  | `reasoning_effort="minimal"` | Cheapest minimal reasoning. ([OpenAI Platform][10])                   |
| `o3-mini-high`                                                     | `o3-mini`                     | `reasoning_effort="high"`    | Small, fast, but think harder. ([OpenAI Platform][11])                |
| `o4-mini-high`                                                     | `o4-mini`                     | `reasoning_effort="high"`    | Cost‑efficient reasoning; push quality. ([OpenAI][12])                |
| *(reserved)* `gpt-5-main`, `gpt-5-main-mini`, `gpt-5-thinking-pro` | —                             | —                            | Placeholders; no direct API model today. Keep reserved. ([OpenAI][8]) |

[1]: https://platform.openai.com/docs/models/gpt-5-chat-latest?utm_source=chatgpt.com "Model - OpenAI API"
[2]: https://platform.openai.com/docs/models/chatgpt-4o-latest?utm_source=chatgpt.com "Model - OpenAI API"
[3]: https://platform.openai.com/docs/models/o3-pro?utm_source=chatgpt.com "Model - OpenAI API"
[4]: https://platform.openai.com/docs/models/o3-deep-research?utm_source=chatgpt.com "o3-deep-research"
[5]: https://platform.openai.com/docs/guides/deep-research?utm_source=chatgpt.com "Deep research - OpenAI API"
[6]: https://platform.openai.com/docs/models/codex-mini-latest?utm_source=chatgpt.com "Codex mini"
[7]: https://platform.openai.com/docs/models/gpt-5?utm_source=chatgpt.com "Model - OpenAI API"
[8]: https://openai.com/index/introducing-gpt-5-for-developers/?utm_source=chatgpt.com "Introducing GPT‑5 for developers"
[9]: https://platform.openai.com/docs/models/gpt-5-mini?utm_source=chatgpt.com "GPT-5 mini"
[10]: https://platform.openai.com/docs/models/gpt-5-nano?utm_source=chatgpt.com "Model - OpenAI API"
[11]: https://platform.openai.com/docs/models/o3-mini?utm_source=chatgpt.com "Model - OpenAI API"
[12]: https://openai.com/index/introducing-o3-and-o4-mini/?utm_source=chatgpt.com "Introducing OpenAI o3 and o4-mini"


# GPT‑5 Model Support

The Responses Manifold supports the current **GPT‑5 family** exposed in the API:

* `gpt-5` *(reasoning model)*
* `gpt-5-mini` *(reasoning model)*
* `gpt-5-nano` *(reasoning model)*
* `gpt-5-chat-latest` *(non‑reasoning ChatGPT variant)*

### Key behavior (practical notes)

* **`gpt-5`, `gpt-5-mini`, and `gpt-5-nano` are reasoning models.** Setting `reasoning_effort="minimal"` reduces thinking but does **not** make them non‑reasoning. For a non‑reasoning chat model, use **`gpt-5-chat-latest`**. [OpenAI][1]
* **Tool calling limitation:** `gpt-5-chat-latest` currently lacks native tool calling (function calls / web search). This is the main gap vs. reasoning models. We expect a future high‑throughput `gpt-5-main`‑style API model may bring tools without reasoning.
* **Latency:** Even with `"minimal"`, GPT‑5 may still “think.” For ultra‑low latency (e.g., Task Models), consider `gpt-4.1-nano` until OpenAI ships a lower‑latency v5 task model.
* **Output style:** `gpt-5-chat-latest` is tuned for polished end‑user chat and usually needs little system prompt. Reasoning models benefit from a short style system prompt (e.g., “concise Markdown with headings and lists”). See `system_prompts` folder in repo for examples.

### GPT‑5 in ChatGPT vs. the API (and a future router)

**In ChatGPT**, “GPT‑5” is a **router** across reasoning, minimal‑reasoning, and non‑reasoning variants based on speed, difficulty, tools, and intent. [More →][1]

**In the API**, you choose explicitly:

* `gpt-5`, `gpt-5-mini`, `gpt-5-nano` — reasoning on by default.
* `reasoning_effort="minimal"` lowers compute but isn’t the same as non‑reasoning ChatGPT.
* The **non‑reasoning** variant is **`gpt-5-chat-latest`**.

> **Note:** The **`gpt-5-auto`** pseudo model currently routes to `gpt-5-chat-latest` and shows a “model router coming soon” notification. A smarter router that selects between GPT‑5 variants is planned.

[1]: https://openai.com/index/introducing-gpt-5-for-developers/ "Introducing GPT‑5 for developers | OpenAI"
[2]: https://cdn.openai.com/pdf/8124a3ce-ab78-4f06-96eb-49ea29ffb52f/gpt5-system-card-aug7.pdf "GPT‑5 System Card (Aug 7, 2025)"

---

## How It Works (Design Notes)

### Persisting non‑message items (function calls, tool outputs, reasoning tokens, …)

The OpenAI Responses API emits **response items** (reasoning, tool calls, tool results, messages) in sequence. Open WebUI normally stores only the final assistant message. Persisting **all** items in order:

* avoids repeated tool calls / re‑reasoning on regeneration,
* improves cache hits (saving \~50–75% input tokens),
* preserves exact model intent.

**Challenge:** Open WebUI’s filter pipeline passes only `messages[] = [{role, content}]`. We need to retain non‑visible items **without** breaking the UI.

### Invisible marker strategy (v2)

Open WebUI ignores Markdown **reference‑style link definitions**, so we embed **invisible markers** in assistant content and store full payloads elsewhere.

* **Persist items** (via `Chats.update_chat_by_id()`) keyed by a **16‑char ID**.
* **Embed markers** into the assistant message content, e.g.:

  ```
  [openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H]: #
  ```
* **Reconstruct history** later by scanning content for markers, loading items by ID, and re‑assembling the sequence.

**Marker format**

```
\n[openai_responses:v2:<item_type>:<id>[?model=<model_id>&k=v...]]: #\n
```

* `<item_type>`: OpenAI event type (`function_call`, `reasoning`, …)
* `<id>`: 16‑char item ID
* optional query params (e.g., `model`)

> **Why not embed JSON?**
> Markers keep the clipboard clean and messages lightweight, while the DB holds the full payloads.

### Example: function call flow

**1) User**

```json
{ "role": "user", "content": "Calculate 34234 multiplied by pi." }
```

**2) OpenAI emits a function call**

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

* Persist with a unique 16‑char ID:

```json
"01HX4Y2VW5VR2Z2H": {
  "model": "gpt-4o",
  "created_at": 1718073601,
  "payload": { "type": "function_call", "...": "..." },
  "message_id": "msg_9fz4qx7e"
}
```

* Emit an invisible marker:

```
[openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H]: #
```

**3) Tool result**

* Persist output, emit a second marker (same pattern).

**4) Assistant (visible)**

```
"34234 multiplied by π ≈ 107,549.28."
```

**Final stream (markers + visible text)**

```
[openai_responses:v2:function_call:01HX4Y2VW5VR2Z2H?model=openai_responses.gpt-4o]: #
[openai_responses:v2:function_call_output:01HX4Y2VW6B091XE?model=openai_responses.gpt-4o]: #
The result of \(34234 \times \pi\) is approximately 107,549.28.
```

**Example Chat DB**

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

> **Tip:** Open browser **DevTools ▸ Network**, open the chat POST, and inspect the stored chat object.

---

## Troubleshooting / FAQ

**Coming soon**