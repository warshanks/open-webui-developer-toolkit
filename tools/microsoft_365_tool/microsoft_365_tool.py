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
from typing import Annotated, Any, Dict, Optional, Literal
from urllib.parse import urlparse


import aiohttp
from cryptography.fernet import Fernet
from pydantic import Field

class Tools:
    def __init__(self):
        MicrosoftAuth.install()  # idempotent    

    async def get_profile(self, __request__) -> str:
        """
        Return the signed-in Microsoft 365 user's profile.
        """
        try:
            # No response passed; MicrosoftAuth handles rotation internally.
            data = await MicrosoftAuth.graph_get(__request__, "/me")
            result = {
                "id": data.get("id"),
                "displayName": data.get("displayName"),
                "mail": data.get("mail"),
                "userPrincipalName": data.get("userPrincipalName"),
                "jobTitle": data.get("jobTitle"),
            }
            return json.dumps({"ok": True, "result": result}, indent=2)
        except MicrosoftAuth.Error as e:
            return json.dumps({"ok": False, "error": str(e)}, indent=2)

    async def search_documents(
        self,
        query: str,  # REQUIRED (no default)
        limit: int = Field(20, ge=1, le=50),  # optional -> strict mode should allow null
        entity: Literal["files", "items", "sites", "all"] = "files",  # enum, optional
        cursor: Optional[str] = None,         # optional + null allowed
        __request__ = None,  # injected, hidden from schema
    ) -> str:
        """
        Search SharePoint/OneDrive documents by keyword (KQL supported).
        :param query: Search text, e.g., filetype:pdf isDocument=true
        :param limit: Number of results to return (1-50)
        :param cursor: Paging token from a previous call
        :return: JSON string with results
        """
        # ---- clamp inputs ----
        size = max(1, min(int(limit), 50))
        query = (query).strip()
        ent = (entity or "files").lower()
        if ent not in ("files", "items", "sites", "all"):
            ent = "files"

        # ---- map entity -> entityTypes ----
        if ent == "files":
            entity_types = ["driveItem"]
        elif ent == "items":
            entity_types = ["listItem"]
        elif ent == "sites":
            entity_types = ["site"]
        else:  # "all"
            entity_types = ["driveItem", "listItem", "list"]

        # ---- lightweight normalizers (kept local so this tool is self-contained) ----
        def _norm_drive_item(di: dict, fallback_id: Optional[str] = None) -> dict:
            fs = di.get("fileSystemInfo") or {}
            file = di.get("file") or {}
            folder = di.get("folder") or {}
            return {
                "id": di.get("id") or fallback_id,
                "name": di.get("name") or di.get("displayName"),
                "webUrl": di.get("webUrl"),
                "modified": di.get("lastModifiedDateTime") or fs.get("lastModifiedDateTime"),
                "size": di.get("size"),
                "mimeType": file.get("mimeType"),
                "driveId": (di.get("parentReference") or {}).get("driveId"),
                "kind": "file" if file else ("folder" if folder else "driveItem"),
                "source": "m365.search",
            }

        def _norm_list_item(li: dict, fallback_id: Optional[str]) -> dict:
            return {
                "id": li.get("id") or fallback_id,
                "name": li.get("name") or ((li.get("fields") or {}).get("title")) or "List item",
                "webUrl": li.get("webUrl"),
                "modified": li.get("lastModifiedDateTime"),
                "size": None,
                "mimeType": None,
                "driveId": None,
                "kind": "listItem",
                "source": "m365.search",
            }

        def _norm_list(lst: dict, fallback_id: Optional[str]) -> dict:
            return {
                "id": lst.get("id") or fallback_id,
                "name": lst.get("name") or lst.get("displayName") or "List",
                "webUrl": lst.get("webUrl"),
                "modified": lst.get("lastModifiedDateTime"),
                "size": None,
                "mimeType": None,
                "driveId": (lst.get("parentReference") or {}).get("driveId"),
                "kind": "list",
                "source": "m365.search",
            }

        def _norm_site(st: dict, fallback_id: Optional[str]) -> dict:
            return {
                "id": st.get("id") or fallback_id,
                "name": st.get("name") or st.get("displayName") or "Site",
                "webUrl": st.get("webUrl"),
                "modified": st.get("lastModifiedDateTime"),
                "size": None,
                "mimeType": None,
                "driveId": None,
                "kind": "site",
                "source": "m365.search",
            }

        def _norm_from_hit(hit: dict) -> Optional[dict]:
            res = hit.get("resource") or {}
            t = (res.get("@odata.type") or "").lower()
            hid = hit.get("hitId")
            if t.endswith("driveitem"):
                # If user chose "files", keep both documents and folders (use KQL isDocument=true in `q` to restrict)
                item = _norm_drive_item(res, fallback_id=hid)
                if hit.get("summary"):
                    item["summary"] = hit.get("summary")
                return item
            if t.endswith("listitem") and ent in ("items", "all"):
                item = _norm_list_item(res, fallback_id=hid)
                if hit.get("summary"):
                    item["summary"] = hit.get("summary")
                return item
            if t.endswith("list") and ent == "all":
                item = _norm_list(res, fallback_id=hid)
                if hit.get("summary"):
                    item["summary"] = hit.get("summary")
                return item
            if t.endswith("site") and ent == "sites":
                item = _norm_site(res, fallback_id=hid)
                if hit.get("summary"):
                    item["summary"] = hit.get("summary")
                return item
            return None

        try:
            # ---- paging: decode cursor or start fresh ----
            if cursor:
                try:
                    tok = json.loads(cursor)
                    if tok.get("t") != "search":
                        return json.dumps({"ok": False, "error": "Invalid cursor."}, indent=2)
                except Exception:
                    return json.dumps({"ok": False, "error": "Invalid cursor."}, indent=2)
                # restore prior params
                q_string = tok.get("q") or "*"
                from_offset = int(tok.get("from") or 0)
                size_now = int(tok.get("size") or size)
                ent = tok.get("entity") or ent
                # re-map entity just in case
                if ent == "files":
                    entity_types = ["driveItem"]
                elif ent == "items":
                    entity_types = ["listItem"]
                elif ent == "sites":
                    entity_types = ["site"]
                else:
                    entity_types = ["driveItem", "listItem", "list"]
            else:
                q_string = query or "*"
                from_offset = 0
                size_now = size

            # ---- build minimal Search API request ----
            body = {
                "requests": [{
                    "entityTypes": entity_types,
                    "query": {"queryString": q_string},
                    "from": from_offset,
                    "size": size_now
                }]
            }

            data = await MicrosoftAuth.graph_post(__request__, "/search/query", json=body)

            # ---- collect hits (flatten all containers just in case) ----
            values = data.get("value") or []
            hits_all = []
            more_any = False
            for v in values:
                for c in (v.get("hitsContainers") or []):
                    hits_all.extend(c.get("hits") or [])
                    more_any = more_any or bool(c.get("moreResultsAvailable"))

            # ---- normalize ----
            results = []
            for h in hits_all:
                item = _norm_from_hit(h)
                if item:
                    results.append(item)

            # ---- next cursor ----
            new_cursor = None
            if more_any or len(results) == size_now:
                new_cursor = json.dumps({
                    "t": "search",
                    "q": q_string,
                    "from": from_offset + len(results),
                    "size": size_now,
                    "entity": ent,
                })

            return json.dumps({"ok": True, "count": len(results), "results": results, "cursor": new_cursor}, indent=2)

        except MicrosoftAuth.Error as e:
            return json.dumps({"ok": False, "error": str(e)}, indent=2)
        


# ----------------------------------------------------------------
# Minimal Microsoft Graph client with OAuth patch for Open WebUI

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
    SCOPES        = os.getenv("MICROSOFT_OAUTH_SCOPE", "").strip()
    WEBUI_SECRET  = os.getenv("WEBUI_SECRET_KEY", "").strip()

    # --- Constants ---
    PROVIDER    = "microsoft"
    COOKIE_NAME = "__Host-ms_graph"
    MAX_AGE     = 90 * 24 * 3600
    GRAPH_BASE  = "https://graph.microsoft.com/v1.0"
    TOKEN_URL   = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    TIMEOUT     = aiohttp.ClientTimeout(total=20)
    USER_AGENT  = f"OpenWebUI-MicrosoftAuth/{__version__}"

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
        except Exception:
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

                # Avoid double-wrapping
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

    # --- Best-effort response discovery (so callers don't need to pass one) ---
    @staticmethod
    def _infer_response(request: Any, provided: Any = None) -> Any | None:
        if provided is not None:
            return provided
        # Common places frameworks stash a response object
        candidates = []
        for obj in (request, getattr(request, "state", None)):
            if not obj:
                continue
            for name in ("response", "_response", "fastapi_response", "starlette_response", "res"):
                try:
                    cand = getattr(obj, name, None)
                    if cand is not None:
                        candidates.append(cand)
                except Exception:
                    pass
        return candidates[0] if candidates else None

    # --- Access token from refresh cookie (auto-rotates cookie if possible) ---
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

        # Try to rotate the cookie when Microsoft returns a new refresh token
        new_rt = data.get("refresh_token")
        resp_obj = cls._infer_response(request, provided=response)
        if resp_obj is not None and new_rt and new_rt != rt and cls._FERNET:
            try:
                enc2 = cls._FERNET.encrypt(
                    json.dumps({"rt": new_rt}, separators=(",", ":")).encode("utf-8")
                ).decode("utf-8")
                resp_obj.set_cookie(
                    key=cls.COOKIE_NAME,
                    value=enc2,
                    httponly=True,
                    secure=True,
                    samesite="Strict",
                    max_age=cls.MAX_AGE,
                    path="/",
                )
            except Exception:
                # Non-fatal: continue without rotation
                pass

        return at

    # --- Minimal Graph GET (accepts @odata.nextLink absolute URLs) ---
    @classmethod
    async def graph_get(
        cls,
        request: Any,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Build URL, allowing only Graph absolute URLs (e.g., @odata.nextLink)
        use_params = params
        if "://" in (path or ""):
            u = urlparse(path)
            base_host = urlparse(cls.GRAPH_BASE).netloc
            if u.scheme != "https" or u.netloc != base_host:
                raise cls.Error("Only Microsoft Graph URLs are allowed for absolute paths.")
            url = path
            # nextLink already contains its own query; don't double-append params
            use_params = None
        else:
            if not path.startswith("/"):
                path = "/" + path
            url = cls.GRAPH_BASE + path

        token = await cls._access_token(request)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": cls.USER_AGENT,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=use_params, headers=headers, timeout=cls.TIMEOUT) as resp:
                if 200 <= resp.status < 300:
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
                raise cls.Error(await cls._err_text(resp))

    # --- Minimal Graph POST (JSON or raw body; allows absolute Graph URLs) ---
    @classmethod
    async def graph_post(
        cls,
        request: Any,
        path: str,
        *,
        json: Any = None,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        # Build URL, allowing only Microsoft Graph absolute URLs
        use_params = params
        if "://" in (path or ""):
            u = urlparse(path)
            base_host = urlparse(cls.GRAPH_BASE).netloc
            if u.scheme != "https" or u.netloc != base_host:
                raise cls.Error("Only Microsoft Graph URLs are allowed for absolute paths.")
            url = path
            # Absolute nextLink/URLs already include their own querystring
            use_params = None
        else:
            if not path.startswith("/"):
                path = "/" + path
            url = cls.GRAPH_BASE + path

        token = await cls._access_token(request)
        h = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": cls.USER_AGENT,
        }
        # Set Content-Type automatically when sending JSON unless caller overrides
        if json is not None and not (headers and "Content-Type" in headers):
            h["Content-Type"] = "application/json"
        if headers:
            h.update(headers)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                params=use_params,
                json=json,
                data=data,
                headers=h,
                timeout=cls.TIMEOUT,
            ) as resp:
                if 200 <= resp.status < 300:
                    # Prefer JSON; fall back to text for non-JSON responses
                    ct = resp.headers.get("Content-Type", "")
                    if "application/json" in ct:
                        try:
                            return await resp.json()
                        except Exception:
                            return {}
                    return {
                        "ok": True,
                        "status": resp.status,
                        "text": await resp.text(),
                    }
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
