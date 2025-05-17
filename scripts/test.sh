#!/usr/bin/env bash
set -euo pipefail

# Lint the codebase first
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"
ruff check .
# Run the pytest suite in verbose mode
pytest -vv tests
