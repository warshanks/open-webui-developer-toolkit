# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into
[Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
bash scripts/test.sh
```

The helper script sets ``PYTHONPATH`` so tests can import from ``src/`` and
executes ``ruff`` for linting, ``unittest`` discovery, and ``pytest`` (limited to
the ``tests/`` folder).
