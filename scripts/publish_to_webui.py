#!/usr/bin/env python3
"""
publish_to_webui.py — Upload or update a single Pipe / Filter / Tool file
to an Open WebUI instance, using only the Python standard library.

Quick CLI:
    WEBUI_URL=https://localhost:8080 \
    WEBUI_KEY=sk_... \
    python scripts/publish_to_webui.py \
        src/openwebui_devtoolkit/pipes/openai_responses_api_pipeline.py

Flags override env-vars if given. The plugin type is auto-detected from the
file path unless --type is provided.

Plugin file **must** contain a front-matter line:
    id: my_plugin_id
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Final

CREATE: Final = "/api/v1/functions/create"
UPDATE: Final = "/api/v1/functions/id/{id}/update"


def _post(base_url: str, api_key: str, path: str, payload: dict) -> int:
    """POST JSON with Bearer auth; return HTTP status code (or raise)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url=base_url.rstrip("/") + path,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Content-Length": str(len(data)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return resp.getcode()
    except urllib.error.HTTPError as e:
        return e.code


def main() -> None:
    p = argparse.ArgumentParser(description="Publish one plugin to Open WebUI")
    p.add_argument("file_path", help="Path to the .py plugin file")
    p.add_argument("--type", choices=("pipe", "filter", "tool"))
    p.add_argument("--url", default=os.getenv("WEBUI_URL", "http://localhost:8080"))
    p.add_argument("--key", default=os.getenv("WEBUI_KEY", ""))
    args = p.parse_args()

    plugin_type = args.type
    if plugin_type is None:
        parts = {part.lower() for part in pathlib.Path(args.file_path).parts}
        if "pipes" in parts:
            plugin_type = "pipe"
        elif "filters" in parts:
            plugin_type = "filter"
        elif "tools" in parts:
            plugin_type = "tool"
        else:
            plugin_type = "pipe"

    if not args.key:
        sys.exit("❌  WEBUI_KEY not set (flag --key or env var)")

    path = pathlib.Path(args.file_path)
    if not path.is_file():
        sys.exit(f"❌  File not found: {path}")

    code = path.read_text(encoding="utf-8")

    # Extract `id:` from header
    plugin_id = next(
        (
            ln.split(":", 1)[1].strip()
            for ln in code.splitlines()
            if ln.lower().startswith("id:")
        ),
        None,
    )
    if not plugin_id:
        sys.exit("❌  'id:' line not found at top of file — aborting")

    payload = {
        "id": plugin_id,
        "name": plugin_id,
        "type": plugin_type,
        "content": code,
        "meta": {"description": "", "manifest": {}},
        "is_active": True,
    }

    # Try to create first
    status = _post(args.url, args.key, CREATE, payload)
    if status == 200:
        print(f"✅  Created '{plugin_id}' on {args.url}")
        return

    # If duplicate ID → update
    if status == 400:
        status = _post(args.url, args.key, UPDATE.format(id=plugin_id), payload)
        if status == 200:
            print(f"🔄  Updated '{plugin_id}' on {args.url}")
            return

    sys.exit(f"❌  WebUI returned HTTP {status}")


if __name__ == "__main__":
    main()
