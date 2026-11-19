# Video Input Filter

Lets video-capable models (for example Kimi K3.1 Pro or GLM 5.3 Flash through
OpenRouter) actually watch attached videos.

Open WebUI only turns image attachments into message content parts. Videos are
stored as-is and reach the model as an `<attached_files>` tag plus an empty RAG
source, so the model knows a file exists but cannot see it. This filter loads
each attached video from storage and appends it to the message that referenced
it as an OpenAI-style `video_url` part with a base64 data URL. Earlier videos in
the conversation are resent each turn, the same way images are.

Only the requesting user's own uploads are sent. Video entries are also removed
from the request's `files` so Open WebUI skips the empty RAG lookup.

## Setup

Add the filter under **Admin ▸ Functions**, enable it, and attach it only to
models that accept video input (model settings ▸ Filters). It is not meant to be
global: models without video support reject `video_url` parts.

## Valves

- `MAX_VIDEO_MB` (default `20`): larger videos are not sent; the model gets a
  note saying why, and the user sees a warning.
- `priority`: execution order among filters.
