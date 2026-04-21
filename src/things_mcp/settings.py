"""
Settings management using pydantic-settings.

Provides type-safe, validated configuration with automatic .env file loading.
Settings are loaded once and cached for the lifetime of the application.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation and .env support.

    Settings are loaded from (in order of priority):
    1. Environment variables
    2. .env file in the project root
    3. Default values defined here

    Environment variables use the same names as the fields (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields (useful for n8n compatibility)
        case_sensitive=False,
    )

    # Server configuration
    things_mcp_host: str = Field(
        default="127.0.0.1",
        description="Host address for the MCP server to bind to",
    )
    things_mcp_port: int = Field(
        default=8009,
        ge=1,
        le=65535,
        description="Port for the MCP server to listen on",
    )
    things_mcp_transport: Literal["streamable-http"] = Field(
        default="streamable-http",
        description="Transport protocol: 'streamable-http' (for Claude Desktop, n8n, ChatGPT)",
    )

    # Things authentication (outbound to Things 3)
    things_auth_token: SecretStr = Field(
        default=SecretStr(""),
        description="Things 3 authentication token (from Things > Settings > General > Enable Things URLs)",
    )

    # Public URL (used as base_url for auth metadata)
    things_mcp_public_url: str = Field(
        default="",
        description="Public HTTPS URL of this server (e.g. https://things.example.com).",
    )

    # MCP API key (bearer token for direct clients)
    things_mcp_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Server API key for bearer-token clients (auto-generated on first run if empty)",
    )

    # Debug settings
    things_mcp_debug: bool = Field(
        default=False,
        description="Enable verbose debug logging to console (default: INFO only)",
    )
    things_mcp_disable_background_osascript: bool = Field(
        default=False,
        description="Disable background AppleScript execution (shows Things in foreground)",
    )

    # Retry configuration
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of retry attempts for failed operations",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Delay between retry attempts in seconds",
    )

    @property
    def has_auth_token(self) -> bool:
        """Check if an authentication token is configured."""
        return bool(self.things_auth_token.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the application settings (cached singleton).

    Returns:
        Settings: The validated application settings.

    Raises:
        ValidationError: If required settings are missing or invalid.
    """
    return Settings()


def get_auth_token() -> str:
    """Get the Things authentication token.

    Convenience function for backwards compatibility.

    Returns:
        str: The authentication token, or empty string if not configured.
    """
    return get_settings().things_auth_token.get_secret_value()


def get_host() -> str:
    """Get the server host address.

    Returns:
        str: The host address to bind to.
    """
    return get_settings().things_mcp_host


def get_port() -> int:
    """Get the server port.

    Returns:
        int: The port number to listen on.
    """
    return get_settings().things_mcp_port


def get_transport() -> Literal["streamable-http"]:
    """Get the transport protocol setting.

    Returns:
        str: The transport protocol to enable (always "streamable-http").
    """
    return get_settings().things_mcp_transport


def get_dashboard_url() -> str:
    """Get the full dashboard URL based on current host/port settings."""
    host = get_settings().things_mcp_host
    port = get_settings().things_mcp_port
    return f"http://{host}:{port}/dashboard"


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled.

    Returns:
        bool: True if debug logging should be enabled.
    """
    return get_settings().things_mcp_debug
