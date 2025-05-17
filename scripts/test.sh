#!/usr/bin/env bash
set -euo pipefail

# Lint the codebase first
# Ensure src/ is on PYTHONPATH for unit tests
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"
ruff check .
# Run the unittest suite
python -m unittest discover -s tests -v
# Also run pytest for extensibility if available. Limit to our tests directory
# so the external WebUI submodule doesn't get picked up.
if command -v pytest >/dev/null 2>&1; then
    pytest -v tests
fi
