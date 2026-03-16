"""Authentication for the MCP server.

Supports two authentication modes simultaneously via MultiAuth:

1. **Keycloak JWT** (for Claude.ai connectors and other OAuth clients):
   Validates JWT tokens issued by a Keycloak authorization server.
   Keycloak handles the full OAuth 2.1 flow (client registration,
   authorization, token issuance). This server only validates the
   resulting JWT tokens using the Keycloak JWKS endpoint.

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
    JWTVerifier,
    MultiAuth,
    RemoteAuthProvider,
    TokenVerifier,
)
from pydantic import AnyHttpUrl

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
) -> MultiAuth:
    """Create the authentication provider.

    Returns a MultiAuth that accepts both:
    - Keycloak JWT clients (Claude.ai) via JWKS-based JWT validation
    - Bearer token clients (Claude Code, n8n) via static API key

    The Keycloak issuer is wrapped in a RemoteAuthProvider so that
    the server advertises RFC 9728 Protected Resource Metadata,
    pointing MCP clients to the Keycloak authorization server for
    token acquisition.

    Args:
        api_key: Static API key for bearer token auth (None to skip).
        base_url: Public URL of this server (e.g. https://things.example.com).
        keycloak_issuer: Keycloak realm issuer URL (e.g. https://auth.example.com/realms/my-realm).
        keycloak_audience: Expected audience claim in JWTs (e.g. mcp-things).
    """
    # Build JWKS URI from Keycloak issuer URL
    jwks_uri = f"{keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"

    jwt_verifier = JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=keycloak_issuer,
        audience=keycloak_audience,
    )

    # Wrap the JWT verifier in a RemoteAuthProvider so the server
    # serves /.well-known/oauth-protected-resource metadata (RFC 9728),
    # telling MCP clients where to obtain tokens.
    keycloak_auth = RemoteAuthProvider(
        token_verifier=jwt_verifier,
        authorization_servers=[AnyHttpUrl(keycloak_issuer)],
        base_url=base_url,
        scopes_supported=["openid"],
        resource_name="Things MCP Server",
    )

    verifiers: list[TokenVerifier] = []
    if api_key:
        verifiers.append(BearerTokenVerifier(api_key))

    return MultiAuth(server=keycloak_auth, verifiers=verifiers)


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"tmcp_{secrets.token_urlsafe(32)}"
