# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into [Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
nox -s lint tests
```

Installing the optional `dev` extras installs the Open WebUI package from the
`external/open-webui` directory so pipelines can import `open_webui` directly. A
scheduled workflow keeps this folder synced with the upstream repository.

`nox` reuses the current Python environment and sets up `PYTHONPATH` so tests run
quickly. `pytest` executes with coverage enabled. Pre-commit hooks run the same
checks so you get fast feedback before committing. Fixtures under `tests/` stub
out `open_webui` so the suite can run without the external project.

## Examples

Example extensions live directly under the `functions/` and `tools/` folders.
Additional files demonstrate advanced features discovered in the
`open-webui` code base:

- `pipes/status_stream_pipe.py` streams tokens and emits status events.
- `filters/stream_logging_filter.py` shows the optional `stream` hook.
- `tools/docstring_tools.py` builds tool specs from function docstrings.
- `tools/universal_example.py` demonstrates valves, event emitters and
  confirmations in one tool.

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
