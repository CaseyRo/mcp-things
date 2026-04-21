"""Authentication for the MCP server.

Uses FastMCP's TokenVerifier to require a static bearer token (API key)
on all /mcp requests. The key is read from THINGS_MCP_API_KEY and
auto-generated on first startup if not set.

Dashboard routes are unauthenticated (they live outside the MCP mount).
"""

import hmac
import os
import secrets
import stat
from pathlib import Path

from fastmcp.server.auth import AccessToken, TokenVerifier

from .logging_config import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "tmcp_"


class BearerTokenVerifier(TokenVerifier):
    """Verify a static bearer token (API key) using timing-safe comparison."""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token, self._api_key):
            return AccessToken(
                token=token,
                client_id="bearer",
                scopes=[],
            )
        return None


def _find_env_file() -> Path:
    """Find the .env file, searching from common locations."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / ".env",
    ]
    for path in candidates:
        if path.exists():
            return path
    return Path(__file__).parent.parent.parent / ".env"


def _write_env_var(env_path: Path, key: str, value: str) -> bool:
    """Write or update a key=value pair in a .env file."""
    try:
        if env_path.exists():
            content = env_path.read_text()
            lines = content.splitlines(keepends=True)
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    found = True
                    break
            if not found:
                prefix = "" if lines and lines[-1].endswith("\n") else "\n"
                lines.append(f"{prefix}{key}={value}\n")
            env_path.write_text("".join(lines))
        else:
            env_path.write_text(f"{key}={value}\n")
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
        return True
    except Exception as e:
        logger.error("Failed to write %s to %s: %s", key, env_path, e)
        return False


def ensure_api_key() -> str:
    """Return the configured API key, auto-generating one if needed.

    If THINGS_MCP_API_KEY is empty/unset, generates a cryptographically
    secure key in the format tmcp_<urlsafe-base64-32>, writes it to .env,
    and updates the environment so pydantic-settings picks it up.
    """
    from .settings import get_settings

    settings = get_settings()
    api_key = settings.things_mcp_api_key.get_secret_value()

    if api_key:
        logger.warning(
            "MCP API key: %s (configure clients with Authorization: Bearer <key>)",
            api_key,
        )
        return api_key

    # Generate a new key
    random_part = secrets.token_urlsafe(32)
    api_key = f"{_KEY_PREFIX}{random_part}"

    env_path = _find_env_file()
    if _write_env_var(env_path, "THINGS_MCP_API_KEY", api_key):
        logger.warning(
            "Generated new MCP API key and saved to %s: %s",
            env_path,
            api_key,
        )
    else:
        logger.warning(
            "Generated new MCP API key (could not save to .env): %s",
            api_key,
        )

    # Update environment so pydantic-settings picks it up
    os.environ["THINGS_MCP_API_KEY"] = api_key
    get_settings.cache_clear()

    return api_key


def create_auth(api_key: str, base_url: str | None = None) -> BearerTokenVerifier:
    """Create the bearer token auth provider for the MCP server."""
    return BearerTokenVerifier(api_key=api_key, base_url=base_url)
