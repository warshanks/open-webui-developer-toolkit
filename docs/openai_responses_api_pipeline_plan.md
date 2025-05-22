# OpenAI Responses API Pipeline Refactor Plan

A short checklist for completing the rewrite of `openai_responses_api_pipeline.py`.

## Goals
- Keep the pipeline as a single file that can be dropped into any WebUI instance.
- Match WebUI's middleware helpers and event ordering.
- Support native tool calls, streaming and usage statistics.
- Simplify the code so it is easier to maintain and test.

## Implementation Outline
1. Extract helpers for assembling the request, streaming SSE and executing tool calls.
2. Rewrite `Pipe.pipe()` to orchestrate these helpers and remove any stored `previous_response_id` once done.
3. Reuse functions from `open_webui.utils.middleware` where they fit.
4. Expand unit tests to cover SSE parsing, tool execution and usage stats.
5. Summarise the new structure in `functions/pipes/README.md`.

## Current Status
- Helper functions exist but the new `pipe()` is still under construction.
- Integration with middleware utilities is partially complete.
- Tests and documentation need to be updated.

## Next Steps
1. Finalise the refactor and ensure events match `process_chat_response`.
2. Add comprehensive tests for streaming and tool flows.
3. Keep this document updated as tasks are finished.
