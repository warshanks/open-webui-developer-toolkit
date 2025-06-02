# OpenAI Responses Manifold

A pipeline that integrates the OpenAI Responses API into Open WebUI. It exposes various OpenAI features such as native tool calling, image generation and web search while keeping compatibility with the WebUI event system.

## Features

| Feature | Status |
| ------- | ------ |
| Web search tool | ✅ Supported |
| Image generation tool | ✅ Supported |
| Native function calling | ✅ Supported |
| Reasoning models | ✅ Supported |
| Reasoning summary | ⚠️ In development |

## Installation

1. Copy `openai_responses_manifold.py` into your Open WebUI instance under **Admin ▸ Pipelines**.
2. Activate the pipe and configure valves as needed.

## Valves

The pipe exposes multiple valves to tweak behaviour. The most common ones are:

- `BASE_URL` – OpenAI API base URL.
- `API_KEY` – API key used for requests.
- `MODEL_ID` – Comma separated model identifiers.
- `ENABLE_WEB_SEARCH` – Turn on the built‑in web search tool.
- `ENABLE_IMAGE_GENERATION` – Enable image generation.
- `ENABLE_NATIVE_TOOL_CALLING` – Use OpenAI's native function calling.
- `ENABLE_REASON_SUMMARY` – Return short reasoning summaries from o-series models.
- `LOG_LEVEL` – Control per‑message logging level.

See the source file for the full list of valves and defaults.

## Stored Response Schema

When a message triggers function calls or other events, the resulting items are
stored in the chat document under `openai_responses_pipe`. Version `2` of the
schema looks like this:

```json
{
  "openai_responses_pipe": {
    "__v": 2,
    "messages": {
      "<message_id>": {
        "model": "o4-mini",
        "created_at": 1719922512,
        "items": [
          {"type": "function_call", ...}
        ]
      }
    }
  }
}
```

Items are stored verbatim as produced by the Responses API to ensure forward
compatibility with new fields and event types.
