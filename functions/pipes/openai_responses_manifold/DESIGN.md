# Design: Filter-Injected Tools via `extra_tools`

## What is this document?
This is a design record that captures the why behind a significant architecture decision in the OpenAI Responses manifold. It is not a how-to guide and does not explain implementation details or usage. The goal is to document context, decision, alternatives, trade-offs, and acceptance criteria so future contributors understand the rationale.

How this document is structured:

- Questions frame the decision and its context.
- Answers describe the intent and rationale, not implementation steps.
- Scope is limited to design motivations and consequences.

---
# Filter-injected tools via `extra_tools`
## Why introduce a separate `extra_tools` field?
`body["tools"]` can be repopulated by Open WebUI before the request leaves the manifold. Filters that attempted to mutate that field would often lose their changes. A dedicated `extra_tools` field gives filters a stable place to add OpenAI-compatible tool specs without racing against internal logic.

## How are tools merged inside the manifold?
The manifold performs a single merge just before sending the request. Tools are collected in this priority order:
1. Open WebUI registry (`__tools__`)
2. Valve-generated tools (web search, remote MCP)
3. Filter-provided `extra_tools`
Later sources override earlier ones. After merging, `extra_tools` is stripped from the body so it never reaches the provider.

## How are conflicts between tools resolved?
Tools are deduplicated by identity:
- Function tools use the key (`"function"`, `name`)
- Non-function tools use (`type`, `None`)
If the same identity appears multiple times, the later entry wins. This allows filters to intentionally override registry or valve tools when necessary.

## What happens if `extra_tools` contains invalid schemas?
The manifold passes `extra_tools` through as-is. Invalid entries may cause provider errors, but they are assumed to be authored by trusted developers. Only minimal shape checking is performed.
