"""Bearer token authentication for the MCP server.

Provides a simple API key authentication mechanism using FastMCP's
TokenVerifier base class. Clients must send:

    Authorization: Bearer <api-key>

The API key is configured via the THINGS_MCP_API_KEY environment variable
or .env file. If not set, the server generates one on first startup and
saves it to .env automatically.
"""

import hmac
import secrets

from fastmcp.server.auth import TokenVerifier, AccessToken

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


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"tmcp_{secrets.token_urlsafe(32)}"
