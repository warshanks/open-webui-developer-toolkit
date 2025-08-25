"""
title: Microsoft 365
id: microsoft_365
author: Justin Kropp
author_url: https://github.com/jrkropp
git_url: https://github.com/jrkropp/open-webui-developer-toolkit/tree/development/tools/microsoft_365_tool
description: Access your Microsoft 365 files, emails, calendar, and Teams directly from Open WebUI.
version: 0.1.0
license: MIT
"""

import os
import json
import base64
import hashlib
from typing import Any, Dict, Optional

import aiohttp
from cryptography.fernet import Fernet

class Tools:
    def __init__(self):
        MicrosoftAuth.install()  # idempotent

    async def list_recent_documents(self, __request__, __response__=None, limit: int = 20, only_files: bool = True) -> str:
        try:
            data = await MicrosoftAuth.graph_get(__request__, "/me/drive/recent", params={"$top": max(1, min(int(limit), 200))}, response=__response__)
            items = data.get("value") or []
            if only_files:
                items = [i for i in items if "file" in i]
            results = [{
                "id": i.get("id"),
                "name": i.get("name"),
                "url": i.get("webUrl"),
                "modified": i.get("lastModifiedDateTime") or (i.get("fileSystemInfo") or {}).get("lastModifiedDateTime"),
                "size": i.get("size"),
                "mimeType": (i.get("file") or {}).get("mimeType"),
            } for i in items]
            return json.dumps({"ok": True, "count": len(results), "results": results}, indent=2)
        except MicrosoftAuth.Error as e:
            return json.dumps({"ok": False, "error": str(e)}, indent=2)


class MicrosoftAuth:
    """
    Minimal, self-contained Graph client for Open WebUI + Azure SSO.
    - Captures refresh_token during OAuth callback, stores encrypted in __Host- cookie.
    - Redeems refresh_token for access_token on demand.
    """
    __version__ = "2025.08.25"

    # --- Required config from environment ---
    TENANT        = os.getenv("MICROSOFT_CLIENT_TENANT_ID", "").strip()
    CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
    CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()
    SCOPES = os.getenv("MICROSOFT_OAUTH_SCOPE", "").strip()
    WEBUI_SECRET  = os.getenv("WEBUI_SECRET_KEY", "").strip()

    # --- Constants ---
    PROVIDER     = "microsoft"
    COOKIE_NAME  = "__Host-ms_graph"
    MAX_AGE      = 90 * 24 * 3600
    GRAPH_BASE   = "https://graph.microsoft.com/v1.0"
    TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    TIMEOUT      = aiohttp.ClientTimeout(total=20)
    USER_AGENT   = f"OpenWebUI-MicrosoftAuth/{__version__}"

    # --- Crypto ---
    if not WEBUI_SECRET:
        _FERNET = None
    else:
        _FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(WEBUI_SECRET.encode("utf-8")).digest()))

    _PATCHED = False

    class Error(Exception):
        pass

    # --- Install a tiny, safe monkey patch ---
    @classmethod
    def install(cls) -> None:
        if cls._PATCHED:
            return
        try:
            from open_webui.utils.oauth import OAuthManager  # type: ignore
        except Exception as e:
            # If OAuthManager is unavailable, we can't capture the token during login.
            # Existing cookie (if present) will still work.
            return

        orig_get_client = OAuthManager.get_client
        orig_handle_cb  = OAuthManager.handle_callback

        def patched_get_client(self_, provider):
            client = orig_get_client(self_, provider)
            if provider == MicrosoftAuth.PROVIDER and hasattr(client, "authorize_access_token"):
                orig = client.authorize_access_token

                async def wrapped_authorize_access_token(request, *args, **kwargs):
                    tok = await orig(request, *args, **kwargs)
                    try:
                        request.state._ms_provider_token = tok  # stash full token result
                    except Exception:
                        pass
                    return tok

                # Mark to avoid double-wrapping
                if getattr(client.authorize_access_token, "__name__", "") != "wrapped_authorize_access_token":
                    client.authorize_access_token = wrapped_authorize_access_token
            return client

        async def patched_handle_callback(self_, request, provider, response):
            resp = await orig_handle_cb(self_, request, provider, response)
            if provider == MicrosoftAuth.PROVIDER and MicrosoftAuth._FERNET:
                try:
                    tok = getattr(getattr(request, "state", object()), "_ms_provider_token", None)
                    rt  = isinstance(tok, dict) and tok.get("refresh_token")
                    if rt:
                        payload = json.dumps({"rt": rt}, separators=(",", ":")).encode("utf-8")
                        enc = MicrosoftAuth._FERNET.encrypt(payload).decode("utf-8")
                        resp.set_cookie(
                            key=MicrosoftAuth.COOKIE_NAME,
                            value=enc,
                            httponly=True,
                            secure=True,
                            samesite="Strict",
                            max_age=MicrosoftAuth.MAX_AGE,
                            path="/",
                        )
                except Exception:
                    # Never break login due to cookie issues
                    pass
            return resp

        OAuthManager.get_client      = patched_get_client
        OAuthManager.handle_callback = patched_handle_callback
        cls._PATCHED = True

    # --- Access token from refresh cookie (optionally rotates refresh cookie) ---
    @classmethod
    async def _access_token(cls, request: Any, response: Any = None) -> str:
        if not cls._FERNET:
            raise cls.Error("WEBUI_SECRET_KEY missing (encryption unavailable).")
        if not (cls.TENANT and cls.CLIENT_ID and cls.CLIENT_SECRET):
            raise cls.Error("Set MICROSOFT_CLIENT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET.")

        enc = getattr(request, "cookies", {}).get(cls.COOKIE_NAME)
        if not enc:
            raise cls.Error(f"Missing {cls.COOKIE_NAME} cookie. Sign in with Microsoft.")

        try:
            payload = cls._FERNET.decrypt(enc.encode("utf-8")).decode("utf-8")
            rt = json.loads(payload)["rt"]
        except Exception:
            raise cls.Error("Invalid or undecryptable token cookie.")

        form = {
            "client_id": cls.CLIENT_ID,
            "client_secret": cls.CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "scope": cls.SCOPES,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(cls.TOKEN_URL, data=form, timeout=cls.TIMEOUT) as r:
                if r.status != 200:
                    raise cls.Error(await cls._err_text(r))
                data = await r.json()

        at = data.get("access_token")
        if not at:
            raise cls.Error("Token refresh returned no access_token.")

        # Optional: rotate cookie if Microsoft returns a new refresh_token
        new_rt = data.get("refresh_token")
        if response is not None and new_rt and new_rt != rt and cls._FERNET:
            try:
                enc2 = cls._FERNET.encrypt(json.dumps({"rt": new_rt}, separators=(",", ":")).encode("utf-8")).decode("utf-8")
                response.set_cookie(
                    key=cls.COOKIE_NAME,
                    value=enc2,
                    httponly=True,
                    secure=True,
                    samesite="Strict",
                    max_age=cls.MAX_AGE,
                    path="/",
                )
            except Exception:
                pass

        return at

    # --- Minimal Graph GET ---
    @classmethod
    async def graph_get(
        cls,
        request: Any,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        response: Any = None,
    ) -> Dict[str, Any]:
        if "://" in (path or ""):
            raise cls.Error("Absolute URLs are not allowed. Use paths like '/me/...'.")
        if not path.startswith("/"):
            path = "/" + path

        token = await cls._access_token(request, response=response)
        url = cls.GRAPH_BASE + path
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": cls.USER_AGENT,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=cls.TIMEOUT) as resp:
                if 200 <= resp.status < 300:
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
                raise cls.Error(await cls._err_text(resp))

    # --- Logout helper ---
    @classmethod
    def clear_cookie(cls, response: Any) -> None:
        response.delete_cookie(cls.COOKIE_NAME, path="/")

    # --- Single error extractor for both token + Graph responses ---
    @staticmethod
    async def _err_text(resp: aiohttp.ClientResponse) -> str:
        try:
            j = await resp.json()
            if isinstance(j, dict):
                return (
                    j.get("error_description")
                    or j.get("message")
                    or (isinstance(j.get("error"), dict) and j["error"].get("message"))
                    or f"HTTP {resp.status}"
                )
        except Exception:
            pass
        return f"HTTP {resp.status}"
