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

*Codex tip:* grep for the **exact filename** you need, e.g.  
`grep -R openai_responses_api_pipeline.py`.

---

## Upstream reference (read-only)
Open WebUI source is included as a shallow submodule in
`external/open-webui/`.
**Codex:** use it for reference only—do **not** edit or commit changes
inside that path.

---

## Tests
Run the test suite with Python’s ``unittest`` module:

```bash
python -m unittest discover -s tests -v
```

All PRs should ensure this command succeeds.

To lint the codebase, run:

```bash
ruff check .
```

