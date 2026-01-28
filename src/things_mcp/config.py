"""
Configuration module for Things MCP.

This module provides backwards compatibility for the config file approach
while delegating to pydantic-settings for the primary configuration.

Priority order for settings:
1. Environment variables (including .env file via pydantic-settings)
2. ~/.things-mcp/config.json file (legacy, for scripts/configure_token.py compatibility)
3. Default values
"""

import json
import logging
from pathlib import Path

from .settings import get_settings

logger = logging.getLogger(__name__)

# Legacy config file support (for configure_token.py)
CONFIG_DIR = Path.home() / ".things-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default configuration values (legacy)
DEFAULT_CONFIG = {
    "things_auth_token": "",
    "retry_attempts": 3,
    "retry_delay": 1.0,
}


def _load_legacy_config() -> dict:
    """Load configuration from legacy config file if it exists."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load legacy config file: {e}")
        return {}


def _save_legacy_config(config: dict) -> bool:
    """Save configuration to legacy config file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save config file: {e}")
        return False


def get_things_auth_token() -> str:
    """Get the Things authentication token.

    Checks in order:
    1. Environment variable / .env (via pydantic-settings)
    2. Legacy config file (~/.things-mcp/config.json)

    Returns:
        str: The authentication token, or empty string if not configured.
    """
    # First check pydantic-settings (env var / .env)
    settings = get_settings()
    if settings.has_auth_token:
        logger.debug("Using Things auth token from environment/.env")
        return settings.things_auth_token

    # Fall back to legacy config file
    legacy_config = _load_legacy_config()
    token = legacy_config.get("things_auth_token", "")
    if token:
        logger.debug("Using Things auth token from legacy config file")
        return token

    logger.warning(
        "No Things auth token found. Set THINGS_AUTH_TOKEN in .env or run scripts/configure_token.py"
    )
    return ""


def set_things_auth_token(token: str) -> bool:
    """Set the Things authentication token in the legacy config file.

    Note: This saves to ~/.things-mcp/config.json for backwards compatibility
    with scripts/configure_token.py. For new setups, prefer using .env file.

    Args:
        token: The authentication token to save.

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    legacy_config = _load_legacy_config()
    legacy_config["things_auth_token"] = token
    return _save_legacy_config(legacy_config)


# Backwards compatibility aliases
def get_config() -> dict:
    """Get current configuration as a dictionary (legacy compatibility)."""
    settings = get_settings()
    return {
        "things_auth_token": get_things_auth_token(),
        "retry_attempts": settings.retry_attempts,
        "retry_delay": settings.retry_delay,
    }


def get_config_value(key: str, default=None):
    """Get a configuration value (legacy compatibility)."""
    config = get_config()
    return config.get(key, default)


def set_config_value(key: str, value) -> bool:
    """Set a configuration value in legacy config file (legacy compatibility)."""
    legacy_config = _load_legacy_config()
    legacy_config[key] = value
    return _save_legacy_config(legacy_config)


def load_config() -> dict:
    """Load configuration (legacy compatibility)."""
    return get_config()


def save_config() -> bool:
    """Save current config to file (legacy compatibility)."""
    return _save_legacy_config(get_config())
