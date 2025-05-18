# Middleware Overview

`backend/open_webui/utils/middleware.py` defines the heart of Open WebUI's chat pipeline.  It wires the chat REST endpoints to a collection of helpers that augment a request, invoke the model and then stream results back to the browser.  The code is long but can be decomposed into a handful of cooperating routines.

## Request lifecycle

1. **Incoming chat request** arrives with model id, message list and optional files or tool specs.
2. `process_chat_payload` is called to enrich and validate the payload. It initializes helper callbacks (`get_event_emitter`, `get_event_call`) and assembles an `extra_params` dict used throughout the rest of the flow.
3. The payload is run through pipeline inlet filters. Tools, image generation, web search and retrieval are triggered as needed.
4. The final payload along with metadata and any events are passed to `generate_chat_completion`.
5. `process_chat_response` handles the streaming or non streaming response. It updates the database, fires websocket events and executes tool calls or the code interpreter where requested.

All of these helpers rely on a small set of utility functions that live in the same module.

## Function reference

### `chat_completion_tools_handler`
Handles function calling when the selected model does not support it natively.

Pseudo-code outline:
```
1. Build a prompt containing JSON tool specs using `tools_function_calling_generation_template`.
2. Call `generate_chat_completion` on the task model.
3. Parse the JSON result; for each returned tool:
   a. Validate parameters against the allowed spec.
   b. Execute the tool either directly or via event emitter.
   c. Capture string results as context snippets or citation sources.
4. Remove any file metadata if a tool handles its own uploads.
5. Return the modified body and a list of citation sources.
```

### `chat_web_search_handler`
Adds web search results to the payload.

1. Emits a `status` event that search is starting.
2. Generates search queries from the latest user message via `generate_queries`.
3. Invokes `process_web_search` which performs the search and stores documents under temporary filenames.
4. Appends file metadata for each search result and emits progress events.
5. Returns the updated form data so later steps can inject the snippets.

### `chat_image_generation_handler`
Optionally produces an image when the client requests it.

1. Emits a `status` event.
2. Optionally calls `generate_image_prompt` to craft a stable diffusion prompt from the conversation.
3. Uses `image_generations` to create the image and emits a `files` event containing its URL.
4. Adds a system message summarizing that an image was generated (or that an error occurred).

### `chat_completion_files_handler`
Retrieves context from user uploaded files or search results.

1. Generates RAG queries from the current conversation.
2. Calls `get_sources_from_files` inside a thread to avoid blocking.
3. The function returns any extracted snippets which later become citation sources.

### `apply_params_to_form_data`
Normalizes user supplied model parameters. It moves items from `form_data['params']` onto OpenAI/Ollama specific fields (`temperature`, `options`, etc.). `logit_bias` strings are converted to JSON when possible.

### `process_chat_payload`
Orchestrates the full inbound flow.

Steps performed:
1. Merge `params` into the form data using `apply_params_to_form_data`.
2. Prepare the `extra_params` dictionary with user info, metadata and event helpers.
3. Choose which models are available (direct single model or global list).
4. If the model defines built‑in knowledge collections, add them to the file list so retrieval can reference them.
5. Pass the payload through `process_pipeline_inlet_filter` so extensions can modify it.
6. Resolve filter functions from the model settings and execute them via `process_filter_functions`.
7. When tools are present and the model cannot handle function calling, `chat_completion_tools_handler` is invoked.
8. If files or web search are requested, call `chat_completion_files_handler` and `chat_web_search_handler` accordingly.
9. Construct RAG context and insert it into the system message using `rag_template` and `add_or_update_system_message`.
10. Return the final form data, metadata and any accumulated events.

### `process_chat_response`
Wraps the model response and streams it back to the client.

1. When the response is non streaming, it schedules `post_response_handler` as a background task.  This task updates chat messages, generates titles or tags and triggers webhook notifications if the user is inactive.
2. For streaming responses the function wraps the generator so each chunk is filtered and forwarded as a websocket event.
3. As tool call blocks are received they are stored, executed and their results inserted back into the conversation. Failed calls retry up to ten times.
4. If code interpreter blocks are enabled they are sent to `execute_code_jupyter` and the resulting output (including generated images) is embedded in the stream.
5. Once the stream finishes a final `chat:completion` event is emitted and the message is persisted.

This multi stage processing allows Open WebUI to offer web search, code execution, retrieval augmented generation and arbitrary tool calls all within a single chat endpoint.

## Event system

`middleware.py` relies heavily on the websocket event helpers `get_event_emitter` and `get_event_call`. These wrap asynchronous queues connected to the user's browser. Each major step (searching, executing a tool, streaming model output) emits structured events so the client can update the UI in real time.

## Background tasks

Longer operations such as database updates, title generation or tag extraction are offloaded using `create_task`. This keeps the HTTP response snappy while ensuring chat history and metadata are stored reliably.

## Deep dive: `process_chat_response`
`process_chat_response` receives the raw model output and turns it into events that the browser understands.  The function distinguishes between streaming and non‑streaming replies, spawns background tasks for post‑processing and wraps streaming generators so every chunk can be filtered and emitted to the websocket.

The inner `post_response_handler` consolidates streamed blocks into full messages:

```python
  1188	        def split_content_and_whitespace(content):
  1189	            content_stripped = content.rstrip()
  1190	            original_whitespace = (
  1191	                content[len(content_stripped) :]
  1192	                if len(content) > len(content_stripped)
  1193	                else ""
  1194	            )
  1195	            return content_stripped, original_whitespace
  1196	
  1197	        def is_opening_code_block(content):
  1198	            backtick_segments = content.split("```")
  1199	            # Even number of segments means the last backticks are opening a new block
  1200	            return len(backtick_segments) > 1 and len(backtick_segments) % 2 == 0
  1201	
  1202	        # Handle as a background task
  1203	        async def post_response_handler(response, events):
  1204	            def serialize_content_blocks(content_blocks, raw=False):
  1205	                content = ""
  1206	
  1207	                for block in content_blocks:
  1208	                    if block["type"] == "text":
```

This handler assembles the streamed `tool_calls`, reasoning blocks and code interpreter output into final messages before persisting them.

When streaming, the original generator is wrapped so extra events can be injected and each chunk is run through any outlet filters:

```python
    else:
        # Fallback to the original response
        async def stream_wrapper(original_generator, events):
            def wrap_item(item):
                return f"data: {item}\n\n"

            for event in events:
                event, _ = await process_filter_functions(
                    request=request,
                    filter_functions=filter_functions,
                    filter_type="stream",
                    form_data=event,
                    extra_params=extra_params,
                )

                if event:
                    yield wrap_item(json.dumps(event))

            async for data in original_generator:
                data, _ = await process_filter_functions(
                    request=request,
                    filter_functions=filter_functions,
                    filter_type="stream",
                    form_data=data,
                    extra_params=extra_params,
                )

                if data:
                    yield data

        return StreamingResponse(
            stream_wrapper(response.body_iterator, events),
            headers=dict(response.headers),
            background=response.background,
        )
```

The wrapper yields any queued events before forwarding chunks from the language model.  Each payload is also passed through configured outlet filters so extensions can modify the stream.
