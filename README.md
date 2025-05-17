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

Minimal example extensions are provided under `examples/`.
Each subfolder (`pipes/`, `filters/`, `tools/`) contains a template
showing how the corresponding feature works.
