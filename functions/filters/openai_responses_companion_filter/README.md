# OpenAI Responses Companion Filter

This filter disables Open WebUI's built-in file injection and system prompt
mutations so that the OpenAI Responses manifold can operate on clean
chat data. It will eventually upload user files directly to OpenAI before
the request reaches the manifold.

## Why a separate filter?

- WebUI's middleware automatically reads uploaded files and inserts their
  content into a RAG system prompt. The Responses API expects raw file
  references instead of injected text.
- The middleware logic runs before any pipe. A filter with
  `file_handler = True` is therefore the only way to intercept the files
  and bypass the RAG mutation.
- By keeping the upload logic out of the pipe we allow the same filter to
  be reused alongside different pipelines.

## Planned responsibilities

**Filter**

1. Mark `file_handler = True` to prevent default file injection.
2. Validate uploads (size and type) and convert images to file objects if
   needed.
3. Upload each file to the OpenAI `/files` API and store the returned IDs
   in the request metadata.
4. Strip the original file objects from the body to reduce memory usage.
5. Leave the rest of the request unchanged for the manifold.

**Pipe**

- Assemble the final payload for the Responses endpoint using the file
  IDs produced by the filter.
- Persist response items and handle streaming, tool calling and history
  reconstruction.
- Avoid dealing with raw uploads; it should only consume already-uploaded
  file references.

Keeping the two concerns separate means future changes—such as new upload
endpoints or file types—can be handled in the filter without touching the
manifold logic.

## Edge cases and future work

- The filter must gracefully handle missing or expired file IDs when
  rebuilding history.
- Large uploads may require chunking or asynchronous processing.
- If the Responses API later accepts inline content, the filter can adapt
  while the pipe remains stable.

Copy `openai_responses_companion_filter.py` to Open WebUI under
**Admin ▸ Filters** to enable.
