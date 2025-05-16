# open-webui-developer-toolkit • Contributor & Agent Guide
Welcome! This repo contains **extensions (pipes, filters, tools)** for  
[Open WebUI](https://github.com/open-webui/open-webui). The codebase is intentionally
thin: one file per extension, with a small helper script to publish to any WebUI
instance.

---

## 1 Repository Map (👀 greppable names)

| Path | What lives here | Agent-safe actions |
|------|-----------------|--------------------|
| **`src/openwebui_devtoolkit/pipes/`** | single-file *pipes* (Python) | add/fix pipe files |
| **`src/openwebui_devtoolkit/filters/`** | single-file *filters* | add/fix filter files |
| **`src/openwebui_devtoolkit/tools/`** | single-file *tools* | add/fix tool files |
| **`scripts/publish_to_webui.py`** | uploader CLI (don’t rename) | edit if API changes |

*Codex tip:* grep for the **exact filename** you need, e.g.  
`grep -R openai_responses_api_pipeline.py`.

---

## 2 Dev Environment in 30 seconds

```bash
python3 -m venv .venv          # one-off
source .venv/bin/activate
pip install -e '.[dev]'        # Ruff, Black, pytest, watchdog
