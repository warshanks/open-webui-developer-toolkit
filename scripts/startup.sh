#!/usr/bin/env bash
set -euo pipefail

echo "▶ Bootstrapping Open WebUI submodule …"
if [ ! -s external/open-webui/.git ]; then
    git submodule update --init --depth 1 external/open-webui
fi

echo "▶ Installing runtime dependencies …"
pip install --quiet ruff httpx fastapi pydantic

echo "▶ Installing toolkit in editable mode …"
pip install -e '.[dev]' --quiet
