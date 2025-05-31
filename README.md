# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into [Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
nox -s lint tests
```

Installing the optional `dev` extras adds linting and testing tools like `ruff`, `pytest` and `nox`.
The `external/open-webui` folder mirrors the upstream project for reference.

`nox` reuses the current Python environment and sets up `PYTHONPATH` so tests run
quickly. `pytest` executes with coverage enabled. Pre-commit hooks run the same
checks so you get fast feedback before committing. Fixtures under `.tests/` stub
out `open_webui` so the suite can run without the external project.

## Examples

Example extensions live under `functions/` and `tools/`. Each pipe now sits in its own folder with a README.
The repository currently includes `functions/pipes/OpenAI Responses Manifold/openai_responses_manifold.py` as a working sample.
Additional examples will be added over time.

## Open WebUI Architecture

Open WebUI is built on a **FastAPI** backend with a **React** front end. The
backend exposes a chat *pipeline* where requests pass through **filters** and a
final **pipe**. Filters can mutate the input and output while the pipe generates
the main response and may invoke tools. The server emits events such as
`message_created` or `tool_started` so the UI can update live. Extensions can
hook into this event system to provide custom behaviour.

Requests and responses are exchanged as JSON. A typical payload sent to a pipe
looks like:

```json
{"chat_id": "123", "message": "hello"}
```

The pipe returns a JSON object such as:

```json
{"message": "hi there"}
```

Additional fields may appear depending on the tool and event systems.

## Documentation
Detailed notes about upstream Open WebUI internals live under `external/`.
See `external/MIDDLEWARE_GUIDE.md` for an overview of the core middleware logic.
The other `*_GUIDE.md` files summarise helper modules from the upstream source.
