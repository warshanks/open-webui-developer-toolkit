# open-webui-developer-toolkit • Contributor & Agent Guide
Welcome! This repo contains **extensions (pipes, filters, tools)** for
[Open WebUI](https://github.com/open-webui/open-webui). The codebase is intentionally
thin: one file per extension, with a small helper script to publish to any WebUI
instance.

---

## Repository Map (👀 greppable names)

| Path | What lives here | Agent-safe actions |
|------|-----------------|--------------------|
| **`src/openwebui_devtoolkit/pipes/`** | single-file *pipes* (Python) | add/fix pipe files |
| **`src/openwebui_devtoolkit/filters/`** | single-file *filters* | add/fix filter files |
| **`src/openwebui_devtoolkit/tools/`** | single-file *tools* | add/fix tool files |
| **`scripts/publish_to_webui.py`** | uploader CLI (don’t rename) | edit if API changes |
| **`docs/`** | notes on upstream middleware & internals | add new docs |

*Codex tip:* grep for the **exact filename** you need, e.g. `grep -R openai_responses_api_pipeline.py`.

---

## Upstream reference (read-only)
Open WebUI source is included as a shallow submodule in `external/open-webui/`.
**Codex:** use it for reference only—do **not** edit or commit changes
inside that path.

---

## Tests
Run linting and tests with ``nox``:

```bash
nox -s lint tests
```

``nox`` uses the current Python environment, adds ``src`` to ``PYTHONPATH``
and executes ``ruff`` followed by ``pytest``. Fixtures in ``tests/conftest.py``
stub out ``open_webui`` so tests stay fast and isolated.
