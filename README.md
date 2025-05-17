# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into [Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
bash scripts/test.sh
```

``scripts/test.sh`` adds ``src`` to ``PYTHONPATH`` so the package can be imported
in tests, runs ``ruff`` for linting and then ``pytest``.  The ``tests``
directory includes fixtures to stub ``open_webui`` so the suite can run without
the external project.
