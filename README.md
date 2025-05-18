# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into [Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
nox -s lint tests
```

`nox` reuses the current Python environment and sets up `PYTHONPATH` so tests run
quickly. `pytest` executes with coverage enabled. Pre-commit hooks run the same
checks so you get fast feedback before committing. Fixtures under `tests/` stub
out `open_webui` so the suite can run without the external project.

## Examples

Minimal example extensions live under `examples/`.
Each subfolder (`pipes/`, `filters/`, `tools/`) contains starter templates.
Additional files demonstrate advanced features discovered in the
`open-webui` code base:

- `pipes/status_stream_pipe.py` streams tokens and emits status events.
- `filters/stream_logging_filter.py` shows the optional `stream` hook.
- `tools/docstring_tools.py` builds tool specs from function docstrings.
- `tools/universal_example.py` demonstrates valves, event emitters and
  confirmations in one tool.

## Documentation

Detailed notes about upstream Open WebUI internals live under `docs/`.
See `docs/middleware.md` for an overview of the core middleware logic.
