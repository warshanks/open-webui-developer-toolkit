#!/usr/bin/env python3
"""
publish_to_webui.py · Upload or update a Pipe / Filter / Tool in Open WebUI.

Quick use:
    ENV_PATH=env/.env.local python scripts/publish_to_webui.py path/to/pipe.py

or let VS Code tasks inject ENV_PATH for you.

Needs:
    pip install requests python-dotenv
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from typing import Final

import requests
from dotenv import load_dotenv
load_dotenv()

CREATE: Final[str] = "/api/v1/functions/create"
UPDATE: Final[str] = "/api/v1/functions/id/{id}/update"


def _post(base_url: str, api_key: str, payload: dict, path: str) -> requests.Response:
    """POST helper with auth header & timeout."""
    return requests.post(
        base_url.rstrip("/") + path,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a plugin to Open WebUI")
    parser.add_argument("file_path", help="Python plugin file to upload")
    # Defaults come from the environment variables we just loaded
    parser.add_argument(
        "--url",
        default=os.getenv("WEBUI_URL", "http://localhost:8080"),
        help="WebUI base URL (env var: WEBUI_URL)",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("WEBUI_KEY", ""),
        help="WebUI API key (env var: WEBUI_KEY)",
    )
    args = parser.parse_args()

    if not args.key:
        sys.exit("❌  No API key provided (flag or WEBUI_KEY env)")

    code_path = pathlib.Path(args.file_path)
    if not code_path.is_file():
        sys.exit(f"❌  File not found: {code_path}")

    code = code_path.read_text(encoding="utf-8")

    # ── 1. Extract front-matter `id:` -------------------------------------------------
    plugin_id = next(
        (
            line.split(":", 1)[1].strip()
            for line in code.splitlines()
            if line.lower().startswith("id:")
        ),
        None,
    )
    if not plugin_id:
        sys.exit("❌  No 'id:' line found at top of the file – aborting")

    payload = {
        "id": plugin_id,
        "name": plugin_id,
        "type": "pipe",  # change to 'filter' or 'tool' if needed
        "content": code,
        "meta": {"description": "", "manifest": {}},
        "is_active": True,
    }

    # ── 2. Try CREATE, then UPDATE if it already exists ------------------------------
    resp = _post(args.url, args.key, payload, CREATE)
    if resp.ok:
        print(f"✅  Created  {plugin_id}")
        return

    if resp.status_code == 400:  # duplicate ID
        resp = _post(args.url, args.key, payload, UPDATE.format(id=plugin_id))
        if resp.ok:
            print(f"🔄  Updated  {plugin_id}")
            return

    # ── 3. Any other error -----------------------------------------------------------
    sys.exit(f"❌  WebUI error {resp.status_code}:\n{resp.text}")


if __name__ == "__main__":
    main()
