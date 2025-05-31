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
2. Install required packages if prompted: `aiohttp` and `orjson`.
3. Activate the pipe and configure valves as needed.

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
