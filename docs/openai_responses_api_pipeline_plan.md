OpenAI Responses API Pipeline Refactor Plan

This refactor aims to make functions/pipes/openai_responses_api_pipeline.py easier to maintain and more closely aligned with WebUI’s built‑in middleware—while remaining a self‑contained, single‑file tool. All changes must preserve existing features such as streaming, parallel tool calls, reasoning summaries (<think> blocks), and usage stats.

⸻

Refactor Goals
	1.	Maintain Single-File Design
So the pipeline can be copied into any Open WebUI instance with minimal friction.
	2.	Align with WebUI Middleware
Match function naming, event emitter patterns, and usage stats tracking so the pipeline behaves like process_chat_response.
	3.	Native Tool Calls
Continue supporting OpenAI’s native function‑call style (tool calls) in an asynchronous, parallel manner.
	4.	Improve Readability & Testability
Break large logic into focused helpers with unit tests to ensure correctness.
	5.	Keep Existing Features
	•	Manual SSE streaming, <think> markers, asynchronous tool calls, web search integration, usage stats, logging, and limiting repeated loops with MAX_TOOL_CALLS.

⸻

High-Level Changes
	1.	Extract Utilities & Mirror Middleware
	•	Use (or closely mimic) utilities from open_webui.utils.middleware.
	•	Remove duplicated code where possible.
	•	Keep all logic in one file (don’t create a separate module).
	2.	Restructure Pipe.pipe()
	•	Break pipe() into smaller helpers:
	•	Input assembly (prepares payload)
	•	Streaming loop (listens to SSE)
	•	Tool execution (runs calls in parallel)
	•	Storage/cleanup (persist or delete partial responses)
	•	Adopt event emitter conventions from WebUI (status, citation, chat:completion).
	3.	Tool Execution Helper
	•	Move _execute_tools to a dedicated helper that accepts a list of calls and returns results.
	•	Store call inputs and outputs in the chat history (e.g., tool_calls, tool_responses fields).
	4.	Reasoning Tokens Persistence
	•	Use previous_response_id and DELETE /v1/responses/{id} to ensure raw reasoning tokens can be streamed and then cleaned up.
	5.	Configuration & Valves
	•	Provide fallback defaults.
	•	Apply user overrides (e.g., UserValves) after defaults are set.
	6.	Testing & Documentation
	•	Add unit tests under .tests/ with SSE parsing, usage stats, and parallel tool calls.
	•	Update functions/pipes/README.md explaining new structure.

⸻

Detailed Implementation Tasks

Below is a task breakdown with suggested statuses. The AI (or human) can check off each item, note partial progress, and leave comments.

Legend for Status:
	•	Not Started
	•	In Progress
	•	Blocked
	•	Done

Task ID	Title	Description	Status	Notes / Links
1	Extract Helpers	1. Create small, focused helper functions for SSE parsing, assembling OpenAI payloads, storing partial messages, etc.  2. Preserve existing logic but isolate it in well‑named functions.  3. Add placeholders in the code for future tests.	Not Started	
2	Refactor pipe()	1. Rewrite Pipe.pipe() to orchestrate the new helpers (payload building, streaming, tool calls, final cleanup).  2. Keep the event emission order consistent with WebUI’s process_chat_response.  3. Ensure partial results are stored properly.	Not Started	
3	Integrate Middleware Imports	1. Identify duplicated logic that can be replaced with open_webui.utils.middleware or similar.  2. Replace references safely, ensuring no feature gaps.	Not Started	
4	Persist Tool Metadata	1. Update tool execution code so tool_calls and tool_responses are stored in the chat DB.  2. Remove any embedded JSON approach if used; rely on database fields for replays.	Not Started	
5	Implement Cleanup	1. After streaming and tool calls, call DELETE /v1/responses/{id} to remove stored responses if previous_response_id was used.  2. Ensure errors do not block cleanup.	Not Started	
6	Expand Unit Tests	1. Add tests under .tests/ mocking SSE events, verifying usage stats and parallel tool call flows.  2. Confirm the final event order (status → message → citation → completion).	Not Started	
7	Update Documentation	1. Revise functions/pipes/README.md with a short summary of the new structure.  2. Note any external imports from middleware.  3. Link to the new test suite for maintainers.	Not Started	
8	Verify Event Logs & Compare	1. Capture logs from a real chat session in both the old pipeline and the new one.  2. Compare event sequences to ensure no regressions.	Not Started	


⸻

Proposed File Structure

Retain one file: openai_responses_api_pipeline.py. Within it:
	1.	Data Models
	•	Valves, UserValves (Pydantic or similar) for configuration.
	•	ResponsesEvent (dataclass) for parsed SSE lines: includes type, delta, etc.
	2.	Helper Functions (for example; names can vary):
	•	assemble_responses_payload(valves: Valves, chat_id: str) -> dict
Builds the input payload for the OpenAI Responses API.
	•	parse_responses_sse(raw_sse_line: str) -> ResponsesEvent
Converts an SSE line into a typed event object.
	•	stream_responses_completion(...) -> AsyncIterator[ResponsesEvent]
Streams SSE from the API, preserves previous_response_id.
	•	execute_responses_tool_calls(tool_calls: list[dict], chat_id: str) -> list[dict]
Runs all requested tools asynchronously and returns results.
	•	delete_openai_response(client, base_url, response_id)
Cleans up stored responses via DELETE /v1/responses/{id}.
	3.	Pipe Class
	•	async def pipe(self, body, __user__, __request__, __emitter__, __caller__, __files__, __meta__, __tools__):
The orchestrator that ties everything together. Steps:
	1.	Load config & chat data
	2.	Assemble the request payload
	3.	Stream & parse SSE events, emit them in real‑time
	4.	Detect and handle tool calls
	5.	Cleanup any stored previous_response_id

⸻

Example Pseudocode for Pipe.pipe()

class Pipe:
    async def pipe(self, body, __user__, __request__, __emitter__, __caller__, __files__, __meta__, __tools__):
        chat_id = __meta__.get("chat_id")
        user_valves = __user__.get("valves", {})
        
        # Merge user overrides
        valves = self._apply_user_overrides(user_valves)
        
        # Prepare the OpenAI payload
        payload = assemble_responses_payload(valves, chat_id)
        payload.update(body)  # Merge user input or instructions if needed

        # Optionally store the previous response
        previous_response_id = None

        # Stream from the OpenAI Responses API
        async for event in stream_responses_completion(
            self.http_client,
            valves.BASE_URL,
            payload,
            previous_response_id
        ):
            # Emit text or citations
            await __emitter__(event.to_dict())
            
            # Check if the event includes any tool calls
            if event.type == "tool_calls":
                # Execute them in parallel
                tool_call_results = await execute_responses_tool_calls(
                    event.data.get("calls"), 
                    chat_id
                )
                # Optionally store or emit the tool results as citations
                # ...
            
            # Update or clear previous_response_id as needed
            previous_response_id = event.data.get("previous_response_id")

        # Cleanup if a stored ID existed
        if previous_response_id:
            await delete_openai_response(self.http_client, valves.BASE_URL, previous_response_id)


⸻

Important Notes
	•	Error Handling:
Even if a tool call fails or the SSE stream breaks, emit a final chat:completion event and attempt to clean up previous_response_id.
	•	MAX_TOOL_CALLS vs. MAX_TOOL_LOOPS:
Consider renaming MAX_TOOL_CALLS to clarify it limits iterative loops of tool calls, not the total possible calls.
	•	Storage of Reasoning Tokens:
Because previous_response_id is used, partial model reasoning stays in the chain of responses. Once we’re done, we issue a DELETE to keep the response store clean.
	•	Logging & Debug:
Maintain the existing debug logging approach. Possibly buffer logs and emit them as a final citation in DEBUG mode.
	•	Parallel Tool Execution:
Use asyncio.gather for tool calls if multiple calls come in at once.

⸻

Next Steps
	•	(1) Begin Helper Extraction: Introduce new helper functions without breaking the old flow.
	•	(2) Incrementally Refactor: Migrate logic from _execute_tools and other large code blocks into the new helpers.
	•	(3) Integrate & Test: Ensure references to new helpers align with WebUI middleware. Write tests as changes are made to prevent regressions.
	•	(4) Finalize & Cleanup: Remove unused code, add docstrings, finalize documentation in README.md.

As each task is completed, update the Task Table’s status column. This will keep the refactoring organized and easy to track.

⸻

End of Plan

Use this document as a single source of truth for the refactoring effort. Each time new commits are made to production, update the “Task ID” row accordingly and note any special considerations in the “Notes / Links” column.
