# Citations Workflow

Open WebUI tags retrieved documents with `<source>` elements and expects the model to reference them using bracketed numbers. The default prompt instructs the model to only cite when the tag includes an `id` attribute:

```
### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [id] **only when the <source> tag includes an explicit id attribute** (e.g., <source id="1">).
```

Source: `config.py` lines 2221‑2241.

During request preparation each document is wrapped in a `<source>` tag and given a numeric index. This happens in `middleware.py`:

```
if len(sources) > 0:
    context_string = ""
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
                    f'<source id="{citation_idx[citation_id]}"' + (f' name="{source_name}"' if source_name else "") + f">{doc_context}</source>\n"
                )
```

Source: `middleware.py` lines 926‑946.

Once prepared, these sources are stored for later and also emitted to the frontend via an event:

```
sources = [source for source in sources if source.get("source", {}).get("name", "") or source.get("source", {}).get("id", "")]
if len(sources) > 0:
    events.append({"sources": sources})
```

Source: `middleware.py` lines 979‑987.

### Frontend

When the frontend receives a `chat:completion` event of type `source`/`citation`, it merges the data into the message object:

```
if (message?.sources) {
    message.sources.push(data);
} else {
    message.sources = [data];
}
```

Source: `Chat.svelte` lines 332‑339.

Before rendering markdown, `[1]`, `[2]` and so on are replaced with inline elements:

```
sourceIds.forEach((sourceId, idx) => {
    const regex = new RegExp(`\\[${idx + 1}\\]`, 'g');
    segment = segment.replace(regex, `<source_id data="${idx + 1}" title="${sourceId}" />`);
});
```

Source: `index.ts` lines 68‑72.

The renderer then turns `<source_id>` tokens into clickable markers. Clicking one scrolls to the related reference:

```
<Source {id} {token} onClick={onSourceClick} />
...
let sourceButton = document.getElementById(`source-${message.id}-${idx}`);
if (sourceButton) {
    sourceButton.click();
} else if (sourcesCollapsible) {
    sourcesCollapsible.querySelector('div:first-child').dispatchEvent(new PointerEvent('pointerup', {}));
}
```

Sources appear at the bottom of each message as numbered buttons. These buttons are generated in `Citations.svelte` and open a modal showing the full snippet when clicked.
