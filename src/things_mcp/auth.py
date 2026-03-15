"""Authentication for the MCP server.

Supports two authentication modes simultaneously via MultiAuth:

1. **OAuth 2.1** (for Claude.ai connectors and other OAuth clients):
   OAuth authorization server with dynamic client registration (MCP spec).
   Claude.ai registers itself automatically. Authorization is auto-approved
   for registered clients. Security layers:
   - Caddy IP allowlist (Anthropic CIDRs + Tailscale) controls network access
   - Client secret (generated during registration) protects token exchange
   - PKCE prevents auth code interception

2. **Bearer token** (for Claude Code, n8n, and other direct clients):
   Simple static API key validation via Authorization: Bearer <key>.

The API key is configured via the THINGS_MCP_API_KEY environment variable
or .env file. If not set, the server generates one on first startup and
saves it to .env automatically.
"""

import hmac
import secrets
import time

from fastmcp.server.auth import (
    AccessToken,
    MultiAuth,
    TokenVerifier,
)
from fastmcp.server.auth.auth import (
    ClientRegistrationOptions,
    OAuthProvider,
    RevocationOptions,
)
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .logging_config import get_logger

logger = get_logger(__name__)

# Token expiration times
AUTH_CODE_EXPIRY = 5 * 60  # 5 minutes
ACCESS_TOKEN_EXPIRY = 60 * 60  # 1 hour
REFRESH_TOKEN_EXPIRY = 30 * 24 * 60 * 60  # 30 days


class ThingsOAuthProvider(OAuthProvider):
    """OAuth 2.1 provider for Things MCP.

    Security model (defense in depth):
    1. Caddy IP allowlist — only Anthropic CIDRs + Tailscale reach the server
    2. Client secret — generated during dynamic registration, required for
       token exchange. Only the client that registered can get tokens.
    3. PKCE — auth codes are bound to the original requester's code_verifier
    4. Short-lived tokens — access tokens expire after 1 hour
    5. In-memory storage — server restart invalidates all sessions
    """

    def __init__(self, base_url: str):
        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["all"],
            ),
            revocation_options=RevocationOptions(enabled=True),
        )
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self._access_to_refresh: dict[str, str] = {}
        self._refresh_to_access: dict[str, str] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a new OAuth client. Only one client allowed at a time.

        First registration wins — subsequent attempts are rejected.
        Restart the server to allow a new client (clears in-memory store).
        """
        if client_info.client_id is None:
            raise ValueError("client_id is required")
        if self.clients:
            logger.warning(
                "Rejected client registration: %s — a client is already registered",
                client_info.client_id,
            )
            raise ValueError(
                "Registration closed: a client is already registered. "
                "Restart the server to allow a new registration."
            )
        self.clients[client_info.client_id] = client_info
        logger.info(
            "Registered OAuth client: %s (%s)",
            client_info.client_id,
            client_info.client_name or "unnamed",
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Auto-approve authorization for registered clients.

        Security is enforced at the network layer (Caddy IP allowlist)
        and token exchange layer (client_secret + PKCE), not here.
        """
        if client.client_id is None or client.client_id not in self.clients:
            raise AuthorizeError(
                error="unauthorized_client",
                error_description="Client not registered.",
            )

        code_value = f"things_code_{secrets.token_hex(16)}"
        scopes = params.scopes if params.scopes is not None else []

        auth_code = AuthorizationCode(
            code=code_value,
            client_id=client.client_id,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            scopes=scopes,
            expires_at=time.time() + AUTH_CODE_EXPIRY,
            code_challenge=params.code_challenge,
        )
        self.auth_codes[code_value] = auth_code
        logger.info("Issued auth code for client %s", client.client_id)

        return construct_redirect_uri(
            str(params.redirect_uri), code=code_value, state=params.state
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if not code:
            return None
        if code.client_id != client.client_id:
            return None
        if code.expires_at < time.time():
            del self.auth_codes[authorization_code]
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if authorization_code.code not in self.auth_codes:
            raise TokenError(
                "invalid_grant", "Authorization code not found or already used."
            )

        # Consume the auth code (one-time use)
        del self.auth_codes[authorization_code.code]

        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")

        access_token_value = f"things_at_{secrets.token_hex(32)}"
        refresh_token_value = f"things_rt_{secrets.token_hex(32)}"

        self.access_tokens[access_token_value] = AccessToken(
            token=access_token_value,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time() + ACCESS_TOKEN_EXPIRY),
        )
        self.refresh_tokens[refresh_token_value] = RefreshToken(
            token=refresh_token_value,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time() + REFRESH_TOKEN_EXPIRY),
        )

        self._access_to_refresh[access_token_value] = refresh_token_value
        self._refresh_to_access[refresh_token_value] = access_token_value

        logger.info("Issued tokens for client %s", client.client_id)

        return OAuthToken(
            access_token=access_token_value,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRY,
            refresh_token=refresh_token_value,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        token = self.refresh_tokens.get(refresh_token)
        if not token:
            return None
        if token.client_id != client.client_id:
            return None
        if token.expires_at is not None and token.expires_at < time.time():
            self._revoke_pair(refresh_token_str=token.token)
            return None
        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if not set(scopes).issubset(set(refresh_token.scopes)):
            raise TokenError(
                "invalid_scope",
                "Requested scopes exceed those authorized.",
            )

        # Rotate tokens
        self._revoke_pair(refresh_token_str=refresh_token.token)

        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")

        new_at = f"things_at_{secrets.token_hex(32)}"
        new_rt = f"things_rt_{secrets.token_hex(32)}"

        self.access_tokens[new_at] = AccessToken(
            token=new_at,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=int(time.time() + ACCESS_TOKEN_EXPIRY),
        )
        self.refresh_tokens[new_rt] = RefreshToken(
            token=new_rt,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=int(time.time() + REFRESH_TOKEN_EXPIRY),
        )

        self._access_to_refresh[new_at] = new_rt
        self._refresh_to_access[new_rt] = new_at

        return OAuthToken(
            access_token=new_at,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRY,
            refresh_token=new_rt,
            scope=" ".join(scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        token_obj = self.access_tokens.get(token)
        if not token_obj:
            return None
        if token_obj.expires_at is not None and token_obj.expires_at < time.time():
            self._revoke_pair(access_token_str=token_obj.token)
            return None
        return token_obj

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            self._revoke_pair(access_token_str=token.token)
        elif isinstance(token, RefreshToken):
            self._revoke_pair(refresh_token_str=token.token)

    def _revoke_pair(
        self, access_token_str: str | None = None, refresh_token_str: str | None = None
    ) -> None:
        """Revoke a token and its paired counterpart."""
        if access_token_str:
            self.access_tokens.pop(access_token_str, None)
            paired_rt = self._access_to_refresh.pop(access_token_str, None)
            if paired_rt:
                self.refresh_tokens.pop(paired_rt, None)
                self._refresh_to_access.pop(paired_rt, None)

        if refresh_token_str:
            self.refresh_tokens.pop(refresh_token_str, None)
            paired_at = self._refresh_to_access.pop(refresh_token_str, None)
            if paired_at:
                self.access_tokens.pop(paired_at, None)
                self._access_to_refresh.pop(paired_at, None)


class BearerTokenVerifier(TokenVerifier):
    """Validates incoming requests against a static API key.

    Uses constant-time comparison to prevent timing attacks.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self._api_key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._api_key):
            logger.warning("Rejected request with invalid API key")
            return None

        return AccessToken(
            token=token,
            client_id="things-mcp-client",
            scopes=["all"],
        )


def create_auth(
    api_key: str | None,
    base_url: str,
    **_kwargs,
) -> MultiAuth:
    """Create the authentication provider.

    Returns a MultiAuth that accepts both:
    - OAuth 2.1 clients (Claude.ai) via dynamic registration + OAuth flow
    - Bearer token clients (Claude Code, n8n) via static API key

    Args:
        api_key: Static API key for bearer token auth (None to skip).
        base_url: Public URL of this server (e.g. https://things.example.com).
    """
    oauth = ThingsOAuthProvider(base_url=base_url)

    if api_key:
        bearer = BearerTokenVerifier(api_key)
        return MultiAuth(server=oauth, verifiers=[bearer])

    return MultiAuth(server=oauth)


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"tmcp_{secrets.token_urlsafe(32)}"
