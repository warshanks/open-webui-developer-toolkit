# Docs

This folder stores internal notes and planning documents for extensions. Files here are not part of the runtime package.

- `pipe_input.md` – details the full structure of arguments passed to a pipe's `pipe()` method.
- `events.md` – how to emit live UI events using `__event_emitter__` and `__event_call__`.
- `file_storage.md` – where uploaded files and generated images are kept and how to attach them to chats.
- `image_generation.md` – notes on OpenAI's image API and the built‑in generation tool.
- `image_compression.md` – explains the client-side resize logic used when the Image Compression setting is enabled.
- `file_handler.md` – how filters and tools disable the built-in file processor.
- `responses_manifold.md` – front-end overview of the OpenAI Responses manifold and why it persists data.
- `message-execution-path.md` – traces a message from the UI through the backend to the database.
- `responses_file_upload.md` – plan for the companion filter that handles file uploads.
- `citations.md` – how sources are inserted, emitted and displayed as inline citations.
