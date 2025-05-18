#!/usr/bin/env python3
"""Upload or update a plugin file on an Open WebUI instance.

The script works with standard library modules only.  A minimal example:

```bash
WEBUI_URL=https://localhost:8080 \
WEBUI_KEY=sk_... \
python .scripts/publish_to_webui.py \
    functions/pipes/openai_responses_api_pipeline.py
```

Flags override the corresponding environment variables.  The plugin type is
auto-detected from the file path when ``--type`` is not provided.

Each plugin file **must** begin with a front‑matter line containing the
plugin ID, for example::

    id: my_plugin_id
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Final

from urllib.error import HTTPError
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CREATE: Final = "/api/v1/functions/create"
UPDATE: Final = "/api/v1/functions/id/{id}/update"


def _post(base_url: str, api_key: str, path: str, payload: dict) -> int:
    """Send a JSON POST request with Bearer auth and return the status code."""

    data = json.dumps(payload).encode()
    req = Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Content-Length": str(len(data)),
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:  # noqa: S310
            return resp.getcode()
    except HTTPError as exc:
        return exc.code

def _parse_args() -> argparse.Namespace:
    """Return CLI arguments."""
    parser = argparse.ArgumentParser(description="Publish one plugin to Open WebUI")
    parser.add_argument("file_path", help="Path to the .py plugin file")
    parser.add_argument("--type", choices=("pipe", "filter", "tool"))
    parser.add_argument("--url", default=os.getenv("WEBUI_URL", "http://localhost:8080"))
    parser.add_argument("--key", default=os.getenv("WEBUI_KEY", ""))
    return parser.parse_args()


def _detect_type(path: Path, explicit: str | None) -> str:
    """Determine the plugin type from the path or an explicit flag."""
    if explicit:
        return explicit
    parts = {part.lower() for part in path.parts}
    if "pipes" in parts:
        return "pipe"
    if "filters" in parts:
        return "filter"
    if "tools" in parts:
        return "tool"
    return "pipe"


def _extract_metadata(code: str) -> tuple[str, str]:
    """Return ``(id, description)`` extracted from the plugin header."""
    plugin_id = next(
        (
            ln.split(":", 1)[1].strip()
            for ln in code.splitlines()
            if ln.lower().startswith("id:")
        ),
        None,
    )
    if not plugin_id:
        raise ValueError("'id:' line not found at top of file -- aborting")

    plugin_description = next(
        (
            ln.split(":", 1)[1].strip()
            for ln in code.splitlines()
            if ln.lower().startswith("description:")
        ),
        "",
    )
    return plugin_id, plugin_description


def _build_payload(plugin_id: str, plugin_type: str, code: str, description: str) -> dict:
    """Create the JSON payload for WebUI."""
    return {
        "id": plugin_id,
        "name": plugin_id,
        "type": plugin_type,
        "content": code,
        "meta": {"description": description, "manifest": {}},
        "is_active": True,
    }


def main() -> None:
    args = _parse_args()

    if not args.key:
        sys.exit("❌  WEBUI_KEY not set (flag --key or env var)")

    path = Path(args.file_path)
    if not path.is_file():
        sys.exit(f"❌  File not found: {path}")
    logging.info("Reading plugin from %s", path)

    code = path.read_text(encoding="utf-8")

    try:
        plugin_id, description = _extract_metadata(code)
        logging.info("Plugin id: %s", plugin_id)
    except ValueError as exc:
        sys.exit(f"❌  {exc}")

    if not description:
        logging.warning("'description:' line not found - using empty description")

    plugin_type = _detect_type(path, args.type)
    payload = _build_payload(plugin_id, plugin_type, code, description)

    logging.info("Publishing '%s' (%s) to %s", plugin_id, plugin_type, args.url)
    status = _post(args.url, args.key, CREATE, payload)
    if status in (200, 201):
        logging.info("Created '%s' on %s [HTTP %s]", plugin_id, args.url, status)
        return

    if status == 400:
        status = _post(args.url, args.key, UPDATE.format(id=plugin_id), payload)
        if status in (200, 201):
            logging.info("Updated '%s' on %s [HTTP %s]", plugin_id, args.url, status)
            return

    sys.exit(f"❌  WebUI returned HTTP {status}")


if __name__ == "__main__":
    main()
