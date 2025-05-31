# Open-WebUI Developer Toolkit

A collection of **pipes**, **filters** and **tools** for extending [Open WebUI](https://github.com/open-webui/open-webui). Every module lives in its own folder so you can copy it directly into a WebUI instance.

```bash
# local development
pip install -e '.[dev]'
nox -s lint tests
```

Installing with the `dev` extras provides `ruff`, `pytest` and `nox`. The `nox` sessions reuse your current Python environment and run the test suite with coverage enabled.

The `external/` directory mirrors the upstream project for reference. **Do not edit** files under `external/open-webui`.

## Repository Layout

- `functions/pipes/` – self‑contained pipes
- `functions/filters/` – reusable filters
- `tools/` – standalone tools
- `docs/` – internal notes and how‑tos

Each subdirectory has a small README explaining its contents.

## Branching Model

This repo uses three long‑lived branches:

1. **`development`** – active development and experiments; may break.
2. **`beta`** – next release candidate. More stable than `development`.
3. **`main`** – production‑ready code pulled from `beta`.

Feature work typically happens in short‑lived branches, merged into `dev` via pull requests. Promote changes from `dev` → `beta` → `main` only after testing.

## Finding Documentation

Additional notes about WebUI internals and example extensions live under `docs/`. Start with `docs/README.md` to see what’s available.
