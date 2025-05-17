# Open-WebUI Developer Toolkit

Self-contained **Pipes**, **Filters**, and **Tools** you can copy-paste into [Open WebUI](https://github.com/open-webui/open-webui) → *Admin ▸ Pipelines*.

```bash
# local dev
pip install -e '.[dev]'
nox -s lint tests
```
GitHub Actions run ``nox`` on every push and pull request. ``nox`` installs the
package in an isolated environment, runs ``ruff`` for linting, and executes the
``pytest`` suite with coverage. The ``tests`` directory includes fixtures to
stub ``open_webui`` so the suite can run without the external project. A
``.pre-commit-config.yaml`` is provided so
you can install pre-commit hooks if desired.
