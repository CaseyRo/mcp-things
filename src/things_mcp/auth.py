"""Authentication for the MCP server.

Supports two authentication modes simultaneously via MultiAuth:

1. **Keycloak OIDC** (for Claude.ai connectors and other OAuth clients):
   The server proxies the full OAuth flow via OIDCProxy using pre-registered
   Keycloak client credentials. No Dynamic Client Registration (DCR) needed.

2. **Bearer token** (for Claude Code, n8n, and other direct clients):
   Simple static API key validation via Authorization: Bearer <key>.

The API key is configured via the THINGS_MCP_API_KEY environment variable
or .env file. If not set, the server generates one on first startup and
saves it to .env automatically.
"""

import hmac
import secrets

from fastmcp.server.auth import (
    AccessToken,
    MultiAuth,
    TokenVerifier,
)
from fastmcp.server.auth.oidc_proxy import OIDCProxy

from .logging_config import get_logger

logger = get_logger(__name__)


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
    keycloak_issuer: str,
    keycloak_audience: str,
    keycloak_client_id: str,
    keycloak_client_secret: str,
) -> MultiAuth:
    """Create the authentication provider.

    Returns a MultiAuth that accepts both:
    - Keycloak OIDC clients (Claude.ai) via OIDCProxy (server-side OAuth)
    - Bearer token clients (Claude Code, n8n) via static API key

    Args:
        api_key: Static API key for bearer token auth (None to skip).
        base_url: Public URL of this server (e.g. https://things.example.com).
        keycloak_issuer: Keycloak realm issuer URL
            (e.g. https://auth.cdit-works.de/realms/cdit-mcp).
        keycloak_audience: Expected JWT audience claim (e.g. mcp-things).
        keycloak_client_id: Pre-registered Keycloak client ID.
        keycloak_client_secret: Keycloak client secret.
    """
    config_url = f"{keycloak_issuer}/.well-known/openid-configuration"

    oidc_auth = OIDCProxy(
        config_url=config_url,
        client_id=keycloak_client_id,
        client_secret=keycloak_client_secret,
        base_url=base_url,
    )

    verifiers: list[TokenVerifier] = []
    if api_key:
        verifiers.append(BearerTokenVerifier(api_key))

    return MultiAuth(server=oidc_auth, verifiers=verifiers)


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"tmcp_{secrets.token_urlsafe(32)}"
