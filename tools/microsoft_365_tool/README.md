# Microsoft 365 Tool

## Overview

This tool demonstrates how to call the Microsoft Graph API from Open WebUI.  It stores the user's Microsoft refresh token in an encrypted, HTTP‑only cookie and uses that token to acquire access tokens on demand.  The example tool exposes a single method, `list_recent_documents`, which fetches `/me/drive/recent` from Microsoft Graph.

> **Note**
> The placeholder Python script provided here does **not** implement the tool.  Drop in the full script to enable the functionality described below.

## Prerequisites

- **Open WebUI** configured with Microsoft/Azure AD single sign‑on.
- The Microsoft provider callback (e.g. `/oauth/callback/microsoft`) must be functioning.
- **Azure App Registration** with delegated permissions and admin consent for:
  - `offline_access` (refresh token)
  - `Files.Read` (add more scopes as needed)
- Client secret created and stored securely.
- The following environment variables must be set in Open WebUI:
  ```bash
  MICROSOFT_CLIENT_TENANT_ID=<your-tenant-guid>
  MICROSOFT_CLIENT_ID=<your-client-id>
  MICROSOFT_CLIENT_SECRET=<your-client-secret>
  MICROSOFT_OAUTH_SCOPE="openid email profile offline_access Mail.Read Files.Read Sites.Read.All Chat.Read Calendars.Read Contacts.Read"
  WEBUI_SECRET_KEY=<super-shared-secret>
  ```

## How the OAuth Monkey Patch Works

Open WebUI normally forwards only an `oauth_id_token` to extensions.  Microsoft issues access tokens that expire after one hour, so any tool that calls the Microsoft Graph API would fail once the token expires.  To work around this, the tool **monkey‑patches** `open_webui.utils.oauth.OAuthManager`:

1. During the OAuth callback, the patch captures the provider's token response, including the `refresh_token` and granted scopes.
2. The refresh token and scopes are encrypted using a Fernet key derived from `WEBUI_SECRET_KEY` and saved as an HTTP‑only cookie (default name `ms_graph`).
3. On each tool invocation, the cookie is decrypted and the refresh token is redeemed for a fresh access token.  If redemption fails due to scope issues, a second attempt is made without explicitly passing scopes.

This approach avoids storing tokens in server‑side state and keeps multiple Open WebUI replicas stateless.

## Usage

Once the full script is added and Open WebUI is configured, enable the tool in the UI and call `list_recent_documents` to retrieve the user's most recently accessed Microsoft 365 files.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
