# OpenAI Responses Manifold

A pipeline that integrates the OpenAI Responses API into Open WebUI. It exposes various OpenAI features such as native tool calling, image generation and web search while keeping compatibility with the WebUI event system.

## Features

| Feature | Status |
| ------- | ------ |
| Web search tool | ✅ Supported |
| Image generation tool | ⚠️ In development |
| Native function calling | ✅ Supported |
| Reasoning models | ✅ Supported |
| Store encrypted reasoning tokens | ✅ Supported |
| Reasoning summaries | ✅ Supported |
| File upload | ⚠️ In development |
| Image input | ⚠️ In development |
| Optimized for token caching | ✅ Supported |

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

## Core Concepts

- **Responses Endpoint** – Uses OpenAI's `responses` API instead of the classic
  completions backend. This unlocks features such as native tool calling,
  reasoning traces and image generation.
- **Valves** – Each configuration option is exposed as a valve so behaviour can
  be tweaked without editing the code. See the source file for defaults.
- **History Reconstruction** – Stored items are replayed when building new
  requests so tools continue exactly where they left off.
- **Tool Result Persistence** – Outputs from tools are kept alongside messages
  which allows them to be shown again later in the UI.
- **Encrypted Reasoning Tokens** – Reasoning models may return an
  `encrypted_content` token which is stored for faster follow‑up queries.

## Changelog

| Version | Highlights |
| ------- | ---------- |
| **1.7.0** | Bind response items to the originating model and improve reasoning token handling. |
| **1.6.0** | Added detailed tag filtering and the ability to remove reasoning blocks from history. |
| **1.5.0** | Introduced model tagging for stored items and expanded test coverage. |
| **1.4.0** | Initial release of the OpenAI Responses Manifold pipeline. |
