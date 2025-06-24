# Citations Example Pipe

## Overview

The Citations Example demonstrates how an Open WebUI pipeline can attach **inline citations** to an assistant's response. This allows the assistant to present answers with references like **\[1]**, **\[2]**, etc., which are clickable and show supporting source snippets. Under the hood, the pipe uses Open WebUI's event emitter system to stream the answer text and **emit citation events** that the frontend parses into interactive references.

### Incremental Citation Events (Streaming)

The approach used in the example emits citations **incrementally** during the streaming of the answer. The advantage of this method is that each reference becomes available as soon as it is mentioned. The user can potentially click on reference **\[1]** as soon as it appears in the text, even while the rest of the answer is still streaming. Under the hood, each `"citation"` event is merged into the message's source list on arrival (see Frontend Handling below). The UI will render the `[1]` marker as a clickable reference shortly after the event is received.

### Single Event Emission (All at Once)

As an alternative, Open WebUI also allows sending all the citations in one go, usually at the end of the answer. Instead of emitting multiple small events, the pipeline can send a **single consolidated event** containing the entire answer and all sources. This is done using the `chat:completion` event type:

* **One final event:** The pipe would construct the full answer with citations and then call `__event_emitter__` once, with `type: "chat:completion"`. In the `data`, it includes the complete answer content (with `[n]` markers included) and a `sources` list containing all citation entries. For example, the event data might look like:

  ```python
  {
    "type": "chat:completion",
    "data": {
        "content": "This example cites two references [1][2].",
        "done": True,
        "sources": [
            { "source": {"name": "Example Source 1"},
              "document": ["Example document snippet one."],
              "metadata": [{"source": "https://example.com/1"}]
            },
            { "source": {"name": "Example Source 2"},
              "document": ["Another snippet from a second source."],
              "metadata": [{"source": "https://example.com/2"}]
            }
        ]
    }
  }
  ```

  (Here `"done": True` signifies the completion of the response stream.) The toolkit documentation shows this exact structure being used in the citations example.

* **Frontend handling:** When this single event is received, the frontend will treat it similarly: it will display the provided `content` as the assistant message and attach the `sources` list to that message. The placeholders `[1]` and `[2]` in the content will be recognized and rendered as citations (just as with the incremental approach).

* **Streaming Incrementally vs all at once** If you use a one-time `chat:completion` event without any prior yielding, the user will see the entire answer appear at once when the event arrives (rather than gradual word-by-word streaming). On the other hand, you can also combine approaches: for instance, *yield* the answer text normally for streaming, and then emit a final `chat:completion` event at the end that contains only the `sources` array. In that hybrid case, you would set the `data.content` to an empty string (`""`) in the final event so that it **does not overwrite** the text already shown, while still delivering the citations list. (Always including a `content` field – even if empty – is advised to avoid frontend issues if the user disconnects mid-stream.) This way, the user gets the benefit of real-time text and then the references pop in once the answer is complete.

Both methods achieve the same end result: the message content contains inline \[number] references, and the message's `sources` data holds the details for each citation. The choice between incremental vs single emission depends on the use case – incremental updates can be more interactive, whereas a single batched update might be simpler for static responses.

## Frontend Handling of Citations

Once the backend emits the citation events (by either method), the Open WebUI frontend takes care of integrating them into the chat display:

* **Merging Citation Events:** The chat client listens for incoming events. The Open WebUI frontend is designed to accept events of type `"source"` or `"citation"` and merge their data into the current assistant message. Essentially, as each citation event arrives, the frontend code appends the provided data entry to the message’s `sources` list. If no sources list exists yet on that message, it will create one. This happens transparently during streaming, before the message rendering is finalized.

* **Rendering Inline Markers:** When the assistant's message is finally rendered, the frontend scans the message text for citation patterns. Any occurrence of **`[n]`** (where *n* is 1, 2, 3, ...) that appears outside of code blocks is identified as a citation marker. The renderer will replace each such token with a special `<source_id>` element that links to the corresponding source data. For example, the text "`46.5 hours [1]`" will be rendered with a clickable reference in place of the literal "\[1]". The mapping is based on the order of the sources: the first source in the list becomes \[1], the second becomes \[2], etc. This is why it’s crucial that numbering in the text and the order of emitted sources align. The frontend explicitly looks for bracketed numbers starting at 1 and increments upward sequentially.

* **Displaying Source Details:** Below each assistant message, the UI will list the unique sources that were cited, typically as a series of numbered buttons or a collapsible "Sources" section. Each source is labeled by its number (and possibly a short name if provided). For instance, you might see a section labeled "Sources" with entries like **\[1] American Automobile Association (AAA)** and **\[2] National Highway Traffic Safety Administration (NHTSA)**. When the user clicks on an inline reference **\[n]** in the message, the interface will scroll to or highlight the corresponding source entry in the list. Conversely, clicking the source entry itself opens a modal window that shows the full text snippet and any metadata for that citation. In our example, clicking the AAA reference would show the sentences about taking breaks every two hours, along with the source URL and date accessed (as provided in the metadata). Clicking the NHTSA reference would show the safety tips snippet, etc. This two-way linkage (inline marker ↔ detailed source view) makes it easy for users to verify and read more about each reference.

* **Source Names and Tooltips:** If a `source.name` was provided in the citation data, the frontend uses it to give context about the reference. The name might be displayed in the sources list and is also used as a tooltip on the inline \[n] marker. For example, hovering over the **\[2]** might show a tooltip saying "National Highway Traffic Safety Administration (NHTSA)" – giving the user a hint about that source even before clicking. This is pulled from the `source: {"name": ...}` field that was emitted.

* **Citations Modal and Metadata:** In the Citations modal (which opens when a reference is clicked), the UI will show the **document snippet** (the content of what was cited) and some metadata fields like the source URL (`metadata.source`) or any other standard fields (e.g., page number or relevance score if present). The example above would show the full sentence from AAA guidance or NHTSA tips, along with the URLs `https://www.aaa.com/safety-tips` or `https://www.nhtsa.gov/road-safety` if those were included. Any metadata keys that the UI doesn't specifically recognize for display will be stored but not shown to the user – this allows developers to attach internal info to citations without cluttering the UI.

In summary, the frontend automatically transforms the model’s answer with `[n]` markers into a richly annotated message. The combination of real-time events and rendering logic results in an assistant message that not only provides an answer but also interactive, trustworthy citations the user can inspect.

## Persistence and Best Practices

When implementing citation events, there are a few additional considerations to ensure everything works smoothly:

* **Use Sequential Numeric Markers:** Always label citations in the text as `[1]`, `[2]`, etc., starting at 1. The Open WebUI renderer looks for increasing integers in square brackets to identify citations. Non-numeric or out-of-order labels will not be recognized as citations.

* **Event Type Compatibility:** Open WebUI now prefers the `"source"` event type name for adding citation data, but it still accepts `"citation"` for backward compatibility. In practice, you can use either. The example pipe uses `"citation"`, which gets handled and stored under the message’s `sources` field (the older `citations` field name has been deprecated in favor of `sources`).

* **Automatic vs Manual Save:** Most custom events (including citation events) are **not persisted** to the database by default. If you want the citations to be available after the session or for later viewing, ensure they get saved. Open WebUI will normally save the final state of the assistant message (including sources) once the response is done. However, to be safe, you can manually save the sources as shown in the example (using the `Chats.upsert_message...` call at the end of the pipe). This covers cases where the streaming might be interrupted or the UI might not automatically save intermediate events. Only certain event types like full message replacements or status updates are auto-saved by the framework, so handling citation persistence explicitly is a good practice.
