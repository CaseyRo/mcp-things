"""Tests for OIDCProxy authentication."""

from unittest.mock import patch


from things_mcp.auth import create_auth


class TestCreateAuth:
    @patch("things_mcp.auth.OIDCProxy")
    def test_returns_oidc_proxy(self, mock_oidc):
        mock_oidc.return_value = "mock_proxy"
        result = create_auth(
            base_url="https://example.com",
            keycloak_issuer="https://auth.example.com/realms/test",
            keycloak_client_id="test-client",
            keycloak_client_secret="secret123",
        )
        mock_oidc.assert_called_once_with(
            config_url="https://auth.example.com/realms/test/.well-known/openid-configuration",
            client_id="test-client",
            client_secret="secret123",
            base_url="https://example.com",
        )
        assert result == "mock_proxy"

    @patch("things_mcp.auth.OIDCProxy")
    def test_config_url_construction(self, mock_oidc):
        create_auth(
            base_url="https://mcp.example.com",
            keycloak_issuer="https://auth.cdit-works.de/realms/cdit-mcp",
            keycloak_client_id="mcp-things",
            keycloak_client_secret="secret",
        )
        call_kwargs = mock_oidc.call_args[1]
        assert call_kwargs["config_url"] == (
            "https://auth.cdit-works.de/realms/cdit-mcp/.well-known/openid-configuration"
        )
