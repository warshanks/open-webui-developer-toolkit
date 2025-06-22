# OpenAI Responses Manifold

*This document explains how the Responses manifold integrates OpenAI's new API with Open WebUI and why responses are stored using a custom schema.*

## Summary

The Responses manifold is a pipeline that replaces Open WebUI's standard completion backend with OpenAI's `responses` endpoint. It adds native tool calling, reasoning models and other advanced features. To use it:

1. Copy `openai_responses_manifold.py` to your WebUI under **Admin ▸ Pipelines**.
2. Activate the pipe and configure any valves such as API key or model IDs.

Once installed, chats behave the same as before but now gain built‑in web search, image generation and function calling when supported by the selected model.

## Why Persist Responses?

OpenAI's API returns rich output items such as function calls, tool responses and reasoning traces. These items need to be stored so the conversation can be replayed accurately. Instead of modifying WebUI's core message schema, the manifold saves them in a dedicated `openai_responses_pipe` section of each chat document. This keeps compatibility with the rest of WebUI and future updates.

### Schema

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

Items are kept verbatim as delivered by the API. When history is rebuilt, these items are inserted before the assistant message that generated them. Because the data sits under its own key, vanilla WebUI installations ignore it gracefully.

## Encrypted Reasoning Tokens

Reasoning models can include an `encrypted_content` field. The manifold stores this encrypted token with each response. OpenAI uses it to cache earlier reasoning steps so follow‑up requests are faster and require less context, improving both speed and quality. Models no longer need to reread their own explanations, giving them more budget for new reasoning in subsequent turns.

## Additional Concepts

- **Valves** – configure endpoints, API keys and optional features like web search or image generation.
- **History Reconstruction** – stored items are reinserted when building the request payload so tools can continue from previous calls.
- **Tool Result Persistence** – by default, tool outputs are appended to the message bucket so the UI can show them again later.
- **Tool Schema Normalization** – the `transform_tools` helper converts WebUI definitions or OpenAI-style lists into the format expected by the Responses API. Enable strict mode to enforce exact field requirements.

More sections will be added here to document advanced usage and troubleshooting.
