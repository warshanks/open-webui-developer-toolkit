# Open-WebUI Developer Toolkit

A collection of **pipes**, **filters** and **tools** for extending [Open WebUI](https://github.com/open-webui/open-webui). Every module lives in its own folder so you can copy it directly into a WebUI instance.

## Repository Layout

- `functions/pipes/` – self‑contained pipes
- `functions/filters/` – reusable filters
- `tools/` – standalone tools
- `docs/` – notes about WebUI internals (useful for those creating their own filters, pipes or tools).

Each subdirectory has a small README explaining its contents.

## Branching Model

This repo uses three long‑lived branches:

1. **`development`** – active development and experiments; may break.
2. **`alpha-preview`** – next release candidate. More stable than `development`.
3. **`main`** – production‑ready code pulled from `alpha-preview`.

Feature work typically happens in short‑lived branches, merged into `development` via pull requests.

Changes flow from `development` → `alpha-preview` → `main` after testing.

## Installing Toolkit Locally (for developers)
```bash
# local development
pip install -e '.[dev]'
nox -s lint tests
```

Installing with the `dev` extras provides `ruff`, `pytest` and `nox`. The `nox` sessions reuse your current Python environment and run the test suite with coverage enabled.

The `external/` directory mirrors a read-only version of upstream Open WebUI repo for reference. Handy for local testing.
