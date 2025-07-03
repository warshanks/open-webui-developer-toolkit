# 📚 How Inline Citations Work in Open WebUI

Open WebUI supports displaying inline citations as numbered references (e.g., `[1]`) within assistant responses. Users can click these references to view detailed source information.

Inline citation functionality consists of the following clear steps:

---
## How Built-In Citations (with RAG / Web Search) work
### Wrapping Snippets in `<source>` Tags

Before passing retrieved snippets into the LLM’s system prompt, Open WebUI explicitly wraps each snippet in numbered `<source>` tags. These tags clearly link each piece of context to a unique citation ID, enabling the LLM to reference sources accurately.

#### Implementation Details:

* Each unique snippet gets assigned a sequential numeric ID, starting from `1`.
* Snippets are placed within `<source>` tags, each explicitly labeled with a unique `id`.
* Optional source names can be included using the `name` attribute.

**Example implementation (`middleware.py`, lines 928–946):**

```python
citation_idx = {}
for source in sources:
    if "document" in source:
        for doc_context, doc_meta in zip(source["document"], source["metadata"]):
            source_name = source.get("source", {}).get("name")
            citation_id = (
                doc_meta.get("source") or source.get("source", {}).get("id") or "N/A"
            )
            if citation_id not in citation_idx:
                citation_idx[citation_id] = len(citation_idx) + 1

            context_string += (
                f'<source id="{citation_idx[citation_id]}"'
                + (f' name="{source_name}"' if source_name else "")
                + f">{doc_context}</source>\n"
            )
```

#### Result:

The resulting context provided to the LLM looks like this:

```html
<source id="1" name="NASA">299,792,458 meters per second is the exact speed of light in vacuum.</source>
<source id="2" name="AAA">AAA recommends taking breaks every two hours while driving.</source>
```

---

### LLM System Prompt & Citation Markers

Open WebUI instructs the LLM through its RAG system prompt to insert inline citation markers `[n]` whenever information from these numbered sources is used in its response.

**Example RAG Template instruction (`config.py`, lines 2218–2248):**

```text
### Task:
Respond using the provided context, adding inline citations [id] only when the <source> tag explicitly contains an id attribute (e.g., <source id="1">).
```

Thus, if the assistant references the first snippet, it includes `[1]` in the answer.

---

Here's the updated, comprehensive section incorporating guidance about disabling built-in citations to avoid conflicts with custom emissions:

---

## 🔧 Emitting Custom Citations (Pipes, Filters, Tools)

Extensions such as **pipes**, **filters**, and **tools** can manually emit custom citation events directly into Open WebUI’s frontend. Citations may be emitted **incrementally** during streaming, or **collectively** at the end of the response.

### ⚠️ Disabling Built-in Citations

When implementing custom citations from a **Tool** or **Filter**, ensure you disable Open WebUI’s built-in citation handling by setting:

```python
def __init__(self):
    self.citation = False  # Disable built-in citations to avoid overwrites
```

**Important:**
* If `self.citation` remains `True` (the default), built-in citations based on your tool’s return value will overwrite any manually emitted citations. Always disable this when managing citations manually.
* You can not [currently] disable citations from a pipe.
  
---

### 📡 Incremental Emission Example (Pipe):

Emit citations immediately after yielding their placeholder within the assistant's response stream:

```python
yield "The speed of light is exactly 299,792,458 m/s [1]."

await __event_emitter__({
    "type": "source",
    "data": {
        "source": {"name": "NASA"},
        "document": ["299,792,458 meters per second is the exact speed of light in vacuum."],
        "metadata": [
            {
                "source": "https://science.nasa.gov/ems/03_movinglight/",
                "date_accessed": "2025-06-24"
            }
        ],
    },
})
```

---

### 📦 Single Emission Example (Pipe, `chat:completion`):

Alternatively, emit all citations together at once, typically at the end of the response stream:

```python
await __event_emitter__({
    "type": "chat:completion",
    "data": {
        "content": "This advice is supported by research [1][2].",
        "done": True,
        "sources": [
            {
                "source": {"name": "Harvard Health"},
                "document": ["Mediterranean diet linked to cardiovascular health."],
                "metadata": [
                    {
                        "source": "https://health.harvard.edu",
                        "date_accessed": "2025-06-24"
                    }
                ],
            },
            {
                "source": {"name": "Mayo Clinic"},
                "document": ["Diet reduces inflammation markers."],
                "metadata": [
                    {
                        "source": "https://mayoclinic.org",
                        "date_accessed": "2025-06-24"
                    }
                ],
            },
        ],
    },
})
```

---

### Frontend Parsing and Rendering

The Open WebUI frontend parses these citation markers (`[1]`, `[2]`, etc.) and renders them as clickable references linked directly to the corresponding sources.

* **Citation events** emitted by the backend (type: `"source"` or `"citation"`) are collected and stored alongside the message content.
* **Markers** are dynamically replaced by clickable UI elements.

**Frontend parsing example (`index.ts`, lines 60–75):**

```typescript
sourceIds.forEach((sourceId, idx) => {
    const regex = new RegExp(`\\[${idx + 1}\\]`, 'g');
    segment = segment.replace(regex, `<source_id data="${idx + 1}" title="${sourceId}" />`);
});
```

When clicked, these references open detailed citation modals displaying snippet text and metadata.

---

---

### Persistence & Best Practices

To ensure citations persist even if the user closes the window mid-response:

* Manually save emitted citations at the end of the pipe:

```python
chat_id = __metadata__.get("chat_id")
message_id = __metadata__.get("message_id")
if chat_id and message_id:
    Chats.upsert_message_to_chat_by_id_and_message_id(
        chat_id, message_id, {"sources": emitted_citations}
    )
```
