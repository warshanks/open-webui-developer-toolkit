# OpenAI Responses API Pipeline Standalone Refactor Plan

This document outlines the proposed refactor for `functions/pipes/openai_responses_api_pipeline.py`. The goal is to make the file feel closer to WebUI's built‑in middleware while remaining completely self contained so it can be copied directly into Open WebUI.

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

5. **Configuration and valves**
   - Review all `Valves` fields and drop or rename any that duplicate middleware options.
   - Provide sensible defaults so a minimal config works out‑of‑the‑box.
   - Ensure user overrides via `UserValves` are applied after initial setup, matching how middleware reads user settings.

6. **Testing**
   - Add unit tests under `.tests/` covering payload building, SSE parsing and tool loops.
   - Reference `external/MIDDLEWARE_GUIDE.md` for examples of mocking the event emitter and chat database.
   - Update `nox -s lint tests` to run these tests.

7. **Documentation**
   - Update `functions/pipes/README.md` with a short section summarising the new structure and pointing to this plan.
   - Note any middleware helpers being imported so future maintainers understand the dependencies.

## Open Questions

- How should error handling mirror middleware behaviour? Investigate how `process_chat_response` updates chat history on failures and replicate that logic for Responses API calls.
- Can reasoning summaries be stored as hidden system messages so later turns can reference them? This might simplify `previous_response_id` handling.

## Next Steps

1. Replace duplicated utilities with imports from middleware where practical.
2. Refactor `openai_responses_api_pipeline.Pipe` to use concise helper functions defined in the same file.
3. Write tests covering the refactored logic.
4. Update documentation.

Future agents should implement the above tasks incrementally, verifying tests pass after each major change.
