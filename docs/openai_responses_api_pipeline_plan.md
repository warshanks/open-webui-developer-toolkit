# OpenAI Responses API Pipeline Standalone Refactor Plan

This document outlines the proposed refactor for `functions/pipes/openai_responses_api_pipeline.py`. The goal is to make the file feel closer to WebUI's built‑in middleware while remaining completely self‑contained so it can be copied directly into Open WebUI.

## Goals

- **Align with WebUI middleware.** Reuse patterns from `open_webui.utils.middleware` to simplify maintenance and share features.
- **Remain a single-file tool.** Avoid creating extra modules so the pipe can be copied as-is.
- **Keep native tool calling.** The pipe must continue to support OpenAI's native tool calls.
- **Improve readability and testability.** Break large blocks of logic into focused helpers and add unit tests.
- **Maintain existing features.** Support reasoning summaries, parallel tool calls, web search integration and usage stats.

## Key Refactor Tasks

1. **Reuse middleware helpers**
   - Import helpers from `open_webui.utils.middleware` instead of duplicating them.
   - Remove local code that mirrors middleware utilities unless slight tweaks are required.
   - Keep any helper functions inside the pipe file so no additional modules are needed.

2. **Restructure `Pipe.pipe()`**
   - Separate the preparation of OpenAI payloads from the streaming loop.
   - Follow the same order as `process_chat_payload` → `generate_chat_completion` → `process_chat_response`.
   - Use small helpers for building `input_items`, assembling `instructions`, preparing tools and updating usage.
   - Limit `Pipe.pipe()` to orchestrating these helpers and emitting events.

3. **Adopt event emitter conventions**
   - Emit `status`, `citation` and `chat:completion` events using the same schemas as the core middleware.
   - When tool calls occur, send events identical to the built‑in `chat_completion_tools_handler` so the UI behaves consistently.
   - Keep the existing `<think>` reasoning markers but ensure they are sent as text deltas.

4. **Tool execution helper**
   - Move `_execute_tools` into a standalone function that mirrors `process_chat_response`’s handling of tool calls.
   - Support parallel execution using `asyncio.gather` and capture outputs as citation sources.
   - Store results back into the chat history via `Chats.upsert_message_to_chat_by_id_and_message_id` similar to middleware behaviour.

5. **Persist reasoning tokens and tool calls**
   - Continue using the `previous_response_id` workaround so raw reasoning tokens can be streamed into follow-up turns.
   - Instead of storing tool call JSON inside citation metadata, upsert the `tool_calls` and `tool_responses` directly into the chat history.
   - Ensure stored items match OpenAI’s expected structure so future API calls can replay the same messages without reconstruction.

6. **Configuration and valves**
   - Provide sensible defaults so a minimal config works out‑of‑the‑box.
   - Ensure user overrides via `UserValves` are applied after initial setup, matching how middleware reads user settings.

7. **Testing**
   - Add unit tests under `.tests/` covering payload building, SSE parsing and tool loops.
   - Reference `external/MIDDLEWARE_GUIDE.md` for examples of mocking the event emitter and chat database.
   - Update `nox -s lint tests` to run these tests.

8. **Documentation**
   - Update `functions/pipes/README.md` with a short section summarising the new structure and pointing to this plan.
   - Note any middleware helpers being imported so future maintainers understand the dependencies.

## Design Notes

- How should error handling mirror middleware behaviour? Investigate how `process_chat_response` updates chat history on failures and replicate that logic for Responses API calls.
- Storing reasoning summaries as system messages is helpful but does not capture the raw reasoning tokens. The pipeline will preserve these tokens using the `previous_response_id` approach so later turns can replay them.
- Tool call payloads and their outputs will be written directly into the chat history via `tool_calls` and `tool_responses`. This removes the need to rebuild message sequences on later turns.

Additional context: using `previous_response_id` requires the chat completion request to be sent with `store=True` so that OpenAI retains the prior response. The pipeline should drop the ID once tools complete and delete the stored response via `DELETE /v1/responses/{id}`.

## Proposed Structure

The refactored file should remain a single module with clear helpers.  
Suggested layout:

1. **Data Models** – Pydantic classes `Valves` and `UserValves` hold
   configuration.  Defaults should match WebUI's middleware so a minimal
   install works without tweaks.
2. **Payload Builders** – helper functions like `build_instructions()`,
   `prepare_tools()` and `assemble_responses_payload()` assemble the model payload.
3. **Streaming Loop** – a `stream_responses_completion()` coroutine yields text
   deltas and preserves reasoning tokens using `previous_response_id`.
4. **Tool Handling** – `execute_responses_tool_calls()` runs tools in parallel and
   updates chat history with `function_call_output` items.
5. **Pipe Class** – lightweight orchestrator exposing a `pipe()` entrypoint
   mirroring WebUI middleware.
6. **Cleanup** – `delete_openai_response()` removes stored responses once
   streaming and tools finish.

Each helper should follow existing middleware naming where possible for easy comparison.

### Key Functions

```python
async def assemble_responses_payload(valves: Valves, chat_id: str) -> dict:
    """Return the input payload for the Responses API."""

async def stream_responses_completion(
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict,
    previous_id: str | None,
) -> AsyncIterator[Event]:
    """Yield SSE events while preserving reasoning tokens."""

async def execute_responses_tool_calls(tool_calls: list[dict], chat_id: str) -> list[dict]:
    """Run tools concurrently and return their results."""

async def delete_openai_response(client: httpx.AsyncClient, base_url: str, response_id: str) -> None:
    """Remove a stored response via the OpenAI API."""

class Pipe:
    async def pipe(self, body: dict, send_event: Callable[[str, Any], Awaitable[None]]):
        """Main entrypoint called by WebUI."""
```

### Detailed Function Outline

Helper names closely mirror the middleware and use a `responses_` prefix where
needed.  This keeps the behaviour comparable while avoiding import collisions if
the pipe is later merged into the core project.

1. `assemble_responses_payload(valves: Valves, chat_id: str) -> dict`
   - Fetch the chat thread and convert it to the Responses API `input` format.
   - Insert the admin system prompt (if any) while respecting any user provided
     system message.
   - Return a payload dictionary ready to be merged with other model parameters.

2. `run_responses_completion(client, base_url, payload, previous_id)`
   - Wrapper around `stream_responses` that yields parsed SSE events.
   - Includes `previous_id` when `store=True` to preserve reasoning tokens.
   - Emits an initial `status` event when the request is accepted.

3. `handle_responses_output(events, chat_id, emitter, tools)`
   - Streams text deltas through `emitter` and records partial messages.
   - Detects `tool_calls` events and delegates to `execute_responses_tool_calls`.
   - Aggregates token usage for the final `chat:completion` event.

4. `execute_responses_tool_calls(tool_calls, chat_id, tools, emitter)`
   - Maps each call to the registered WebUI tools and runs them in parallel.
   - Stores results under `function_call_output` in the chat history.
   - Emits `citation` events referencing the returned data.

5. `cleanup_responses(client, base_url, previous_id)`
   - Deletes stored responses via `DELETE /v1/responses/{id}` once they are no
     longer needed.

### Previous Response Tracking

`stream_responses_completion()` accepts a `previous_id` argument when `store=True`.
The function reuses this ID with OpenAI's `previous_response_id` field so that raw reasoning tokens persist across tool loops.  
Once the tool step is finished the ID can be dropped, keeping history size small.
With the new `DELETE /v1/responses/{id}` endpoint the pipe can remove stored responses when they are no longer needed. Use this after tool execution to prevent history bloat.

### Event Flow Example

The refactored pipeline should emit events in a predictable sequence so the
frontend can mirror the behaviour of WebUI's middleware:

1. **`status`** – immediately after the Responses request is accepted. Indicates
   the model is generating output.
2. **`message`** – streamed deltas of assistant text or `<think>` blocks.
3. **`citation`** – whenever a web search or tool result produces a source
   document. These should also be persisted via `_store_citation`.
4. **`chat:completion`** – final usage stats followed by a final event with
   `{"done": true}`.

Tools emit their own `status` updates while running. The order of events should
match `process_chat_response` so existing UI components require no changes.

## Next Steps

1. Replace duplicated utilities with imports from middleware where practical.
2. Refactor `openai_responses_api_pipeline.Pipe` to use concise helper functions defined in the same file.
3. Write tests covering the refactored logic.
4. Update documentation.
5. Validate the emitted event order matches `process_chat_response` using unit
   tests and sample logs.

Future agents should implement the above tasks incrementally, verifying tests pass after each major change.
