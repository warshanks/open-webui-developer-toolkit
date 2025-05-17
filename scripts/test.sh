#!/usr/bin/env bash
set -euo pipefail

# Lint the codebase first
# Ensure src/ is on PYTHONPATH for unit tests
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"
ruff check .
# Run the test suite
python -m unittest discover -s tests -v
