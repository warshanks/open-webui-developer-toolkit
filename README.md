# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into
[Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
bash scripts/test.sh
```

The script sets ``PYTHONPATH`` so tests can import from ``src/`` and runs
``ruff`` followed by the unit tests.
