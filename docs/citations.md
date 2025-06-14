# Citation Flow in Open WebUI

This document traces how source documents are attached to a chat request, emitted as events and rendered as clickable references.

## 1. RAG template

The default template instructs the model to cite only when the `<source>` tag has an `id` attribute:

```text
### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [id] **only when the <source> tag includes an explicit id attribute** (e.g., <source id="1">).
```

Source: `config.py` lines 2218‑2248.

## 2. Building `<source>` tags

During request preparation each retrieved snippet is wrapped in a `<source>` tag. Unique sources are indexed starting from 1 and optional names are preserved:

```python
citation_idx = {}
for source in sources:
    if "document" in source:
        for doc_context, doc_meta in zip(source["document"], source["metadata"]):
            source_name = source.get("source", {}).get("name", None)
            citation_id = (
                doc_meta.get("source", None)
                or source.get("source", {}).get("id", None)
                or "N/A"
            )
            if citation_id not in citation_idx:
                citation_idx[citation_id] = len(citation_idx) + 1
            context_string += (
                f'<source id="{citation_idx[citation_id]}"'
                + (f' name="{source_name}"' if source_name else "")
                + f">{doc_context}</source>\n"
            )
```

Source: `middleware.py` lines 928‑946.

## 3. Emitting citation events

After inserting the context the backend keeps the source list and sends it to the client before streaming the assistant response:

```python
sources = [
    s for s in sources
    if s.get("source", {}).get("name", "") or s.get("source", {}).get("id", "")
]
if len(sources) > 0:
    events.append({"sources": sources})
```

Source: `middleware.py` lines 979‑987.

`process_chat_response` later emits these extra events alongside the normal `chat:completion` stream so the frontend stores them with the message.

## 4. Frontend message updates

The chat event handler merges incoming citation events into the message object:

```svelte
if (message?.sources) {
    message.sources.push(data);
} else {
    message.sources = [data];
}
```

Source: `Chat.svelte` lines 334‑339.

## 5. Replacing bracket markers

`ContentRenderer.svelte` compiles a list of source display names and passes them to the Markdown renderer. For each `[n]` found outside code blocks a `<source_id>` element is inserted:

```typescript
sourceIds.forEach((sourceId, idx) => {
    const regex = new RegExp(`\\[${idx + 1}\\]`, 'g');
    segment = segment.replace(regex, `<source_id data="${idx + 1}" title="${sourceId}" />`);
});
```

Source: `index.ts` lines 60‑75.

`HTMLToken.svelte` renders these markers using the `<Source>` component which calls `onSourceClick` when clicked.

## 6. Clicking a citation

`ResponseMessage.svelte` handles the click by scrolling to the corresponding reference button. If the "Sources" section is collapsed it briefly opens it first:

```svelte
let sourceButton = document.getElementById(`source-${message.id}-${idx}`);
const sourcesCollapsible = document.getElementById(`collapsible-${message.id}`);
if (sourceButton) {
    sourceButton.click();
} else if (sourcesCollapsible) {
    sourcesCollapsible.querySelector('div:first-child').dispatchEvent(new PointerEvent('pointerup', {}));
    await new Promise((resolve) => {
        requestAnimationFrame(() => {
            requestAnimationFrame(resolve);
        });
    });
    sourceButton = document.getElementById(`source-${message.id}-${idx}`);
    sourceButton && sourceButton.click();
}
```

Source: `ResponseMessage.svelte` lines 818‑831.

## 7. Viewing the source

Below each assistant message `Citations.svelte` lists unique sources as numbered buttons. Clicking one opens `CitationsModal.svelte`, displaying the full text snippet, metadata such as page numbers and any relevance scores.

Unknown metadata keys are kept with the message but are not shown in the modal, allowing extensions to attach hidden data to citations.
