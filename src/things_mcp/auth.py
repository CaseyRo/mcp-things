"""Authentication for the MCP server.

Uses OIDCProxy to proxy the OAuth flow to Keycloak using pre-registered
client credentials. Claude.ai (and Claude Code through it) authenticates
via the standard authorization_code flow.
"""

from fastmcp.server.auth.oidc_proxy import OIDCProxy

from .logging_config import get_logger

logger = get_logger(__name__)


def create_auth(
    base_url: str,
    keycloak_issuer: str,
    keycloak_client_id: str,
    keycloak_client_secret: str,
) -> OIDCProxy:
    """Create the OIDCProxy authentication provider.

    Args:
        base_url: Public URL of this server (e.g. https://things.example.com).
        keycloak_issuer: Keycloak realm issuer URL
            (e.g. https://auth.cdit-works.de/realms/cdit-mcp).
        keycloak_client_id: Pre-registered Keycloak client ID.
        keycloak_client_secret: Keycloak client secret.
    """
    config_url = f"{keycloak_issuer}/.well-known/openid-configuration"

    return OIDCProxy(
        config_url=config_url,
        client_id=keycloak_client_id,
        client_secret=keycloak_client_secret,
        base_url=base_url,
    )
