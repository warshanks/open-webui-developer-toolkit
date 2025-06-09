# Open-WebUI Developer Toolkit

A collection of **pipes**, **filters** and **tools** for extending [Open WebUI](https://github.com/open-webui/open-webui). Every module lives in its own folder so you can copy it directly into a WebUI instance.

## Repository Layout

- `functions/pipes/` – self‑contained pipes
- `functions/filters/` – reusable filters
- `tools/` – standalone tools
- `docs/` – notes about WebUI internals (useful for those creating their own filters, pipes or tools).

Each subdirectory has a small README explaining its contents.

## Available Extensions

| Name | Description | Links |
| --- | --- | --- |
| Input Inspector | Shows pipe input arguments as citations for debugging. | [Stable](https://github.com/jrkropp/open-webui-developer-toolkit/tree/main/functions/pipes/input_inspector) (main)<br>[Preview](https://github.com/jrkropp/open-webui-developer-toolkit/tree/alpha-preview/functions/pipes/input_inspector) (alpha-preview) |
| OpenAI Responses Manifold | OpenAI Reasponse API pipe. | [Stable](https://github.com/jrkropp/open-webui-developer-toolkit/tree/main/functions/pipes/openai_responses_manifold) (main)<br>[Preview](https://github.com/jrkropp/open-webui-developer-toolkit/tree/alpha-preview/functions/pipes/openai_responses_manifold) (alpha-preview) |
| Reason Toggle Filter | Filter toggle that temporarily routes a request to another model. | [Stable](https://github.com/jrkropp/open-webui-developer-toolkit/tree/main/functions/filters/reason_toggle_filter) (main) <br>[Preview](https://github.com/jrkropp/open-webui-developer-toolkit/tree/alpha-preview/functions/filters/reason_toggle_filter) (alpha-preview) |

## Branching Model

This repository uses three primary branches:

1. **`main`**
   Production-ready and stable code.

2. **`alpha-preview`**
   Next release candidate. Tested, pre-production code.

3. **`development`**
   Active development, experimentation, and potentially unstable changes.

  ```
   development (continuous changes) → alpha-preview (2–3 weeks testing) → main (stable)
  ```

## Installing Toolkit Locally (for developers)
```bash
# local development
pip install -e '.[dev]'
nox -s lint tests
```

Installing with the `dev` extras provides `ruff`, `pytest` and `nox`. The `nox` sessions reuse your current Python environment and run the test suite with coverage enabled.

The `external/` directory mirrors a read-only version of upstream Open WebUI repo for reference. Handy for local testing.
