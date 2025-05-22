# Split streaming logic in OpenAI Responses pipe

This document outlines the refactor to handle streaming and non-streaming
responses separately.

## Motivation
The existing `Pipe.pipe()` mixes logic for normal responses and Server-Sent
Events. Separating these paths will make the code easier to follow and simpler
to extend.

## Proposed changes
1. **Introduce two helper methods**:
   - `_streaming_response(...)` – implements the current streaming loop.
   - `_non_streaming_response(...)` – wraps the existing `get_responses()` call
     and yields the final text.
2. **Switch `pipe()`** to check `body.get("stream", False)` and delegate to the
   appropriate helper.
3. Each helper will receive the prepared request parameters, http client and
   emitter so the main method only handles setup and cleanup logic.
4. Keep the existing event emission and usage accounting inside the helpers so
   behaviour remains unchanged.

This refactor keeps the public interface intact while isolating the two code
paths for easier maintenance.

## Implementation Steps
1. Move the non-streaming branch of `pipe()` into
   `Pipe._non_stream_response(...)`. The method should:
   - call `get_responses()`
   - emit usage stats and completion events
   - yield the final assistant text when available.
2. Move the current streaming loop into
   `Pipe._stream_response(...)`. It retains the SSE handling and tool
   call logic unchanged.
3. In `Pipe.pipe()`, compute shared variables and assemble the request
   payload. Then delegate to one of the helpers using
   `if body.get("stream", False):`.
4. Both helpers return an async generator yielding text chunks so the
   caller can iterate normally.
