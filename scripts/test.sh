#!/usr/bin/env bash
set -euo pipefail

# Lint the codebase first
# Ensure src/ is on PYTHONPATH for unit tests
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"
ruff check .
# Run the unittest suite
python -m unittest discover -s tests -v
# Also run pytest for extensibility if available
if command -v pytest >/dev/null 2>&1; then
    pytest -v
fi
