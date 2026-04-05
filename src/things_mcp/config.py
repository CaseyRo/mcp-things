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
import os
import stat
import sys
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
    """Save configuration to legacy config file with restrictive permissions."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.chmod(stat.S_IRWXU)  # 0700
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
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


def _find_env_file() -> Path:
    """Find the .env file, searching from the working directory upward."""
    # Check common locations
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / ".env",  # project root
    ]
    for path in candidates:
        if path.exists():
            return path
    # Default to project root
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
        logger.error(f"Failed to write {key} to {env_path}: {e}")
        return False


def _write_token_to_env(token: str) -> bool:
    """Write or update THINGS_AUTH_TOKEN in the .env file."""
    return _write_env_var(_find_env_file(), "THINGS_AUTH_TOKEN", token)


def enforce_file_permissions() -> None:
    """Check and fix permissions on sensitive files at startup."""
    files_0600 = [
        _find_env_file(),
        CONFIG_FILE,
    ]
    dirs_0700 = [
        CONFIG_DIR,
        Path.home() / ".things-mcp" / "logs",
    ]

    for d in dirs_0700:
        if d.exists() and (d.stat().st_mode & 0o077) != 0:
            d.chmod(stat.S_IRWXU)
            logger.warning("Fixed insecure directory permissions: %s", d)

    for f in files_0600:
        if f.exists() and (f.stat().st_mode & 0o077) != 0:
            f.chmod(stat.S_IRUSR | stat.S_IWUSR)
            logger.warning("Fixed insecure file permissions: %s", f)

    # Fix log files
    logs_dir = Path.home() / ".things-mcp" / "logs"
    if logs_dir.exists():
        for log_file in logs_dir.iterdir():
            if log_file.is_file() and (log_file.stat().st_mode & 0o077) != 0:
                log_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
                logger.warning("Fixed insecure log file permissions: %s", log_file)

    # Fix DLQ file
    dlq_file = Path.home() / ".things-mcp" / "things_dlq.json"
    if dlq_file.exists() and (dlq_file.stat().st_mode & 0o077) != 0:
        dlq_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        logger.warning("Fixed insecure DLQ file permissions: %s", dlq_file)


def ensure_auth_token() -> str:
    """Check for auth token at startup; prompt interactively if missing.

    Returns the token, or exits if none provided and stdin is a terminal.
    If stdin is not a terminal (e.g. running as a service), logs an error
    and returns empty string to let the caller decide.
    """
    token = get_things_auth_token()
    if token:
        return token

    # Non-interactive: can't prompt
    if not sys.stdin.isatty():
        logger.error(
            "No THINGS_AUTH_TOKEN configured. "
            "Set it in .env or run: python scripts/configure_token.py"
        )
        return ""

    # Interactive prompt
    print("\n" + "=" * 50)
    print("  Things MCP - Auth Token Required")
    print("=" * 50)
    print("\nNo authentication token found.")
    print("Find it in: Things 3 → Settings → General → Enable Things URLs")
    print("\nPaste your token (or Ctrl+C to quit):")

    try:
        new_token = input("> ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        sys.exit(1)

    if not new_token:
        print("\nNo token provided. Server cannot start without it.")
        sys.exit(1)

    # Reject tokens with newlines/carriage returns to prevent env var injection
    if "\n" in new_token or "\r" in new_token:
        print("\nInvalid token (contains newline characters).")
        sys.exit(1)

    # Save to .env
    env_path = _find_env_file()
    if _write_token_to_env(new_token):
        print(f"Token saved to {env_path}")
    else:
        print("Warning: Could not save to .env, using token for this session only.")

    # Update the environment so pydantic-settings picks it up
    os.environ["THINGS_AUTH_TOKEN"] = new_token
    get_settings.cache_clear()

    print("Continuing startup...\n")
    return new_token
