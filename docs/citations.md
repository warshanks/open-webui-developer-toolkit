# Citations in Open WebUI

This guide describes how citations work within Open WebUI, including built-in handling and custom emission from backend components such as **pipes**, **filters**, and **tools**.

---

## 📚 Overview

Open WebUI supports **inline citations**, allowing assistants to reference external sources directly within chat messages. Citations are displayed as numbered markers (e.g., `[1]`) and clickable references that show detailed source information in a modal window.

There are two main ways citations are handled:

* **Built-in Citations (RAG Templates)**: Automatically provided by built-in retrieval augmented generation (RAG) processes.
* **Custom Citations (Event Emission)**: Manually emitted by pipes, filters, or tools via events.

---

## ✨ How Built-in Citations Work

### 1. RAG Template

Open WebUI instructs the assistant model to insert inline citations **only if** the provided context snippet has a unique source ID:

```text
### Task:
Respond using the provided context, adding inline citations [id] only when the <source> tag explicitly contains an id attribute (e.g., <source id="1">).
```

*Source: `config.py` lines 2218–2248.*

### 2. Generating `<source>` Tags

Retrieved snippets are wrapped with numbered `<source>` tags, each having a unique, sequentially increasing ID.

**Example implementation:**

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

*Source: `middleware.py` lines 928–946.*

---

## 🛠️ Emitting Custom Citations

Pipes, tools, and filters can manually emit citations via events. Open WebUI supports two main approaches:

### A. Incremental Emission (Streaming)

Emit each citation individually as it occurs during response streaming.

**Example (Pipe):**

```python
# 1. Yield citation placeholder in response
yield "The speed of light is exactly 299,792,458 m/s [1]."

# 2. Emit corresponding citation immediately
if __event_emitter__:
    await __event_emitter__({
        "type": "source",
        "data": {
            "source": {"name": "NASA"},
            "document": [
                "299,792,458 meters per second is the exact speed of light in vacuum."
            ],
            "metadata": [
                {
                    "source": "https://science.nasa.gov/ems/03_movinglight/",
                    "date_accessed": "2025-06-24"
                }
            ],
        },
    })
```

### B. Single Emission (All at Once)

Emit citations collectively at the end of the response. This can be combined with incremental text streaming or sent as one complete event.

**Example (Pipe using `chat:completion`):**

```python
await __event_emitter__({
    "type": "chat:completion",
    "data": {
        "content": "Here’s some health advice based on research [1][2].",
        "done": True,
        "sources": [
            {
                "source": {"name": "Harvard Health"},
                "document": ["Mediterranean diet linked to improved cardiovascular outcomes."],
                "metadata": [{"source": "https://health.harvard.edu", "date_accessed": "2025-06-24"}],
            },
            {
                "source": {"name": "Mayo Clinic"},
                "document": ["Mediterranean diet reduces inflammation markers."],
                "metadata": [{"source": "https://mayoclinic.org", "date_accessed": "2025-06-24"}],
            },
        ],
    },
})
```

**Hybrid Approach:**
You can also stream text incrementally and emit citations at the end with an empty `content` field to prevent overwriting the previously streamed text.

---

## 🌐 Frontend Handling of Citations

Open WebUI’s frontend automatically integrates citation data emitted by the backend:

### 1. Merging Citation Events

The frontend listens for citation events (`"source"` or `"citation"`) and appends them to the current message’s `sources` list.

```svelte
if (type === 'source' || type === 'citation') {
    if (message?.sources) {
        message.sources.push(data);
    } else {
        message.sources = [data];
    }
}
```

*Source: `Chat.svelte` lines 316–339.*

### 2. Rendering Inline Citations

When rendering messages, the frontend scans for citation markers (`[1]`, `[2]`, etc.) and transforms them into clickable links that open detailed modals:

```typescript
// Replace citation markers with interactive elements
sourceIds.forEach((sourceId, idx) => {
    const regex = new RegExp(`\\[${idx + 1}\\]`, 'g');
    segment = segment.replace(regex, `<source_id data="${idx + 1}" title="${sourceId}" />`);
});
```

*Source: `index.ts` lines 60–75.*

### 3. Citations Modal Display

Clicking a citation opens a modal showing the snippet text and metadata like URLs, timestamps, and additional details.

---

## 📦 Persistence and Best Practices

* **Always number citations sequentially** `[1]`, `[2]`, `[3]`, etc.
* **Include empty `content`** in `chat:completion` if only sending citations (prevents UI freezes).
* **Manually persist citations** in the pipe for robustness, ensuring they remain available even if the user exits mid-response:

```python
chat_id = __metadata__.get("chat_id")
message_id = __metadata__.get("message_id")
if chat_id and message_id:
    Chats.upsert_message_to_chat_by_id_and_message_id(
        chat_id, message_id, {"sources": emitted_citations}
    )
```

---

## 🚩 Minimal Complete Example Pipe

A simplified, real-world streaming citation pipe:

```python
class Pipe:
    async def pipe(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __metadata__: dict[str, Any] | None = None,
        *_,
    ) -> AsyncGenerator[Any, None]:

        response = "Traveling 2790 miles at 60 mph takes about 46.5 hours [1]."
        citation = {
            "source": {"name": "Calculator Tool"},
            "document": ["Evaluated expression '2790 miles / 60 mph = 46.5 hours'"],
            "metadata": [{"tool": "calculator", "date_accessed": datetime.datetime.utcnow().isoformat()}],
        }

        for word in response.split():
            yield word + " "
            if word.strip(".,!?") == "[1]" and __event_emitter__:
                await __event_emitter__({"type": "source", "data": citation})
```
