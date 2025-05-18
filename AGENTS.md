# open-webui-developer-toolkit • Contributor & Agent Guide

Welcome! This repo contains **extensions (pipes, filters, tools)** for
[Open WebUI](https://github.com/open-webui/open-webui). Each extension is a
single Python file. A helper script under `scripts/` publishes the files to a
running WebUI instance.

---

## Repository Map (👀 greppable names)

| Path | What lives here | Agent-safe actions |
|------|-----------------|--------------------|
| **`functions/pipes/`** | single-file *pipes* (Python) | add/fix pipe files |
| **`functions/filters/`** | single-file *filters* | add/fix filter files |
| **`tools/`** | standalone *tools* | add/fix tool files |
| **`open-webui-reference/`** | upstream architecture notes | add new docs |
| **`scripts/publish_to_webui.py`** | uploader CLI (don’t rename) | edit if API changes |
| **`docs/`** | additional internal notes | add new docs |

*Codex tip:* grep for the **exact filename** you need, e.g. `grep -R openai_responses_api_pipeline.py`.

---

## Upstream reference (read-only)
If present, the `open-webui/` folder mirrors the upstream project. Use it for
reference only—do **not** edit or commit changes inside that path.

---

## Tests
Run linting and tests with `nox`:

```bash
nox -s lint tests
```

`nox` uses the current Python environment, adds `src` to `PYTHONPATH` and
executes `ruff` followed by `pytest`. Fixtures in `tests/conftest.py` stub out
`open_webui` so tests stay fast and isolated.
