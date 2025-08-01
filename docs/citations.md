# 📚 Inline Citations in Open WebUI

Open WebUI supports inline citations displayed as numbered references (e.g., `[1]`) within assistant responses. Users can click these references to view detailed source information.

This guide covers:

* Built-in citations (RAG/Web Search)
* Custom citations (emitted via Pipes, Filters, Tools)
* Frontend parsing and persistence

> 📖 **Further Reading:** [Citations Pipe Example](functions/pipes/citations_example)

---

## 🔍 Built-In Citations (RAG/Web Search)

Open WebUI automatically generates inline citations using context snippets wrapped in `<source>` tags.

### Step 1: Wrapping Snippets in `<source>` Tags

Retrieved snippets are explicitly wrapped in numbered `<source>` tags before being passed to the LLM’s system prompt. This allows the LLM to accurately reference each snippet.

**Implementation Details:**

* Assign sequential numeric IDs starting from `1`.
* Use `<source>` tags with a unique `id` attribute.
* Optionally include source names via the `name` attribute.

**Example (`middleware.py`, lines 928–946):**

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

**Resulting Context Example:**

```html
<source id="1" name="NASA">299,792,458 meters per second is the exact speed of light in vacuum.</source>
<source id="2" name="AAA">AAA recommends taking breaks every two hours while driving.</source>
```

### Step 2: System Prompt and Inline Citation Markers

The LLM is instructed to insert inline citation markers `[n]` whenever referencing content from numbered `<source>` tags.

**System Prompt Example (`config.py`, lines 2218–2248):**

```text
### Task:
Respond using the provided context, adding inline citations [id] only when the <source> tag explicitly contains an id attribute (e.g., <source id="1">).
```

Thus, referencing the first snippet results in a `[1]` citation in the assistant response.

---

## 🔧 Custom Citations (Pipes, Filters, Tools)

Extensions like **pipes**, **filters**, and **tools** can manually emit citations directly to the frontend, either incrementally or collectively.

### ⚠️ Important: Disable Built-in Citations

When emitting custom citations from **Tools** or **Filters**, disable Open WebUI’s built-in citation handling to avoid conflicts:

```python
def __init__(self):
    self.citation = False  # Prevent built-in citation overwrite
```

**Note:**
* Currently, you cannot disable built-in citations from pipes.

---

### 📡 Emitting Custom Citations: Examples

Custom citations can be emitted incrementally or as a single event.

#### Incremental Emission (Pipes)

Emit citations immediately after yielding placeholder text:

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

#### Single Emission (Pipe, `chat:completion` event)

Emit all citations simultaneously, typically at the end of streaming:

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

## ⚙️ Backend Citation Handling

Inline citation metadata is generated server‑side in
`backend/open_webui/utils/middleware.py`.

1. **Collecting sources** – tools and retrieval steps append dictionaries to a
   `sources` array. Tool output is wrapped using logic around lines 253–267:
   ```python
   sources.append({
       "source": {"name": f"TOOL:{tool_name}"},
       "document": [tool_result],
       "metadata": [{"source": f"TOOL:{tool_name}", "parameters": tool_function_params}],
       "tool_result": True,
   })
   ```【F:external/open-webui/backend/open_webui/utils/middleware.py†L253-L267】

2. **Assigning citation numbers** – when sources exist, a `citation_idx_map`
   assigns each unique `metadata.source` or `source.id` a sequential number. Each
   snippet is wrapped with `<source id="n">` where `n` is the assigned index:
   ```python
   citation_idx_map = {}
   for source in sources:
       is_tool_result = source.get("tool_result", False)
       if "document" in source and not is_tool_result:
           for document_text, document_metadata in zip(source["document"], source["metadata"]):
               source_name = source.get("source", {}).get("name", None)
               source_id = (
                   document_metadata.get("source", None)
                   or source.get("source", {}).get("id", None)
                   or "N/A"
               )
               if source_id not in citation_idx_map:
                   citation_idx_map[source_id] = len(citation_idx_map) + 1
               context_string += (
                   f'<source id="{citation_idx_map[source_id]}"'
                   + (f' name="{source_name}"' if source_name else "")
                   + f">{document_text}</source>\n"
               )
   ```【F:external/open-webui/backend/open_webui/utils/middleware.py†L956-L981】

3. **Emitting citation data** – after context construction the `sources` array
   is attached to chat events so the frontend can render modals
   (lines&nbsp;1013–1021):
   ```python
   sources = [s for s in sources if s.get("source", {}).get("name", "") or s.get("source", {}).get("id", "")]
   if len(sources) > 0:
       events.append({"sources": sources})
   ```【F:external/open-webui/backend/open_webui/utils/middleware.py†L1013-L1021】

The system prompt instructing the model to add `[n]` markers when a matching
`<source id="n">` tag exists is defined in
`backend/open_webui/config.py` around lines&nbsp;2320–2358.

---

## 🖥 Frontend Parsing & Rendering

The frontend parses inline citation markers `[1]`, `[2]`, etc., and renders them as clickable references.

**Frontend Behavior:**

* **Citation events** (`type: "source"` or `"citation"`) are collected and stored.
* **Markers** in message content become clickable UI elements linking to citation details.

**Frontend Parsing Example (`index.ts`, lines 60–75):**

```typescript
sourceIds.forEach((sourceId, idx) => {
    const regex = new RegExp(`\\[${idx + 1}\\]`, 'g');
    segment = segment.replace(regex, `<source_id data="${idx + 1}" title="${sourceId}" />`);
});
```

The `replaceTokens` helper at
`src/lib/utils/index.ts` performs this replacement and ensures that numbers map
to the collected `sourceIds` list.【F:external/open-webui/src/lib/utils/index.ts†L33-L78】

`ContentRenderer.svelte` builds `sourceIds` from the incoming citation payload.
When `metadata.name` is present it is used; otherwise the UI falls back to the
top-level `source.name` or raw `metadata.source` URL. This logic lives around
lines&nbsp;136–165:
```svelte
sourceIds={(sources ?? []).reduce((acc, s) => {
    let ids = [];
    s.document.forEach((document, index) => {
        const metadata = s.metadata?.[index];
        const id = metadata?.source ?? 'N/A';
        if (metadata?.name) {
            ids.push(metadata.name);
            return ids;
        }
        if (id.startsWith('http://') || id.startsWith('https://')) {
            ids.push(id);
        } else {
            ids.push(s?.source?.name ?? id);
        }
        return ids;
    });
    acc = [...acc, ...ids];
    return acc.filter((item, index) => acc.indexOf(item) === index);
}, [])}
```【F:external/open-webui/src/lib/components/chat/Messages/ContentRenderer.svelte†L136-L165】

`Citations.svelte` groups multiple documents under the same `id` so that one
reference can represent several snippets. The reducer between lines 45–88 merges
documents sharing a common `metadata.source` or `source.id` into a single entry.
```svelte
citations = sources.reduce((acc, source) => {
    source.document.forEach((document, index) => {
        const metadata = source.metadata?.[index];
        const id = metadata?.source ?? source?.source?.id ?? 'N/A';
        let _source = source?.source;
        if (metadata?.name) {
            _source = { ..._source, name: metadata.name };
        }
        if (id.startsWith('http://') || id.startsWith('https://')) {
            _source = { ..._source, name: id, url: id };
        }
        const existingSource = acc.find((item) => item.id === id);
        if (existingSource) {
            existingSource.document.push(document);
            existingSource.metadata.push(metadata);
            if (distance !== undefined) existingSource.distances.push(distance);
        } else {
            acc.push({ id, source: _source, document: [document], metadata: metadata ? [metadata] : [], distances: distance !== undefined ? [distance] : undefined });
        }
    });
    return acc;
}, []);
```【F:external/open-webui/src/lib/components/chat/Messages/Citations.svelte†L45-L88】

Clicking a reference opens a detailed modal displaying the grouped source snippet
and metadata.

---

## 💾 Persistence & Best Practices

To ensure citations persist even if the user interrupts the response:

* Manually save emitted citations at the end of the pipe:

```python
chat_id = __metadata__.get("chat_id")
message_id = __metadata__.get("message_id")
if chat_id and message_id:
    Chats.upsert_message_to_chat_by_id_and_message_id(
        chat_id, message_id, {"sources": emitted_citations}
    )
```
