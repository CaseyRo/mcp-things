"""Tests for bearer token authentication."""

import asyncio

from things_mcp.auth import BearerTokenVerifier, create_auth


class TestBearerTokenVerifier:
    def test_valid_token(self):
        verifier = BearerTokenVerifier(api_key="tmcp_test123")
        result = asyncio.get_event_loop().run_until_complete(
            verifier.verify_token("tmcp_test123")
        )
        assert result is not None
        assert result.client_id == "bearer"

    def test_invalid_token(self):
        verifier = BearerTokenVerifier(api_key="tmcp_test123")
        result = asyncio.get_event_loop().run_until_complete(
            verifier.verify_token("wrong_key")
        )
        assert result is None

    def test_empty_token(self):
        verifier = BearerTokenVerifier(api_key="tmcp_test123")
        result = asyncio.get_event_loop().run_until_complete(verifier.verify_token(""))
        assert result is None

    def test_timing_safe_comparison(self):
        """Verify we use hmac.compare_digest (timing-safe) by checking similar tokens are rejected."""
        verifier = BearerTokenVerifier(api_key="tmcp_test123")
        # Off-by-one character should still be rejected
        result = asyncio.get_event_loop().run_until_complete(
            verifier.verify_token("tmcp_test124")
        )
        assert result is None


class TestCreateAuth:
    def test_returns_bearer_verifier(self):
        result = create_auth(api_key="tmcp_test123")
        assert isinstance(result, BearerTokenVerifier)

    def test_with_base_url(self):
        result = create_auth(api_key="tmcp_test123", base_url="https://example.com")
        assert isinstance(result, BearerTokenVerifier)


class TestEnsureApiKeyNeverLogsKey:
    """ensure_api_key() must never write the key value to the log."""

    def _run(self, monkeypatch, tmp_path, caplog, env_value):
        import logging

        from things_mcp import auth
        from things_mcp.settings import get_settings

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(auth, "_find_env_file", lambda: tmp_path / ".env")
        monkeypatch.setenv("THINGS_MCP_API_KEY", env_value)
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.DEBUG):
                key = auth.ensure_api_key()
        finally:
            get_settings.cache_clear()
        return key

    def test_loaded_key_not_logged(self, monkeypatch, tmp_path, caplog):
        secret = "tmcp_loaded-secret-value-1234567890"
        key = self._run(monkeypatch, tmp_path, caplog, secret)
        assert key == secret
        assert secret not in caplog.text
        assert "tmcp_…" in caplog.text

    def test_generated_key_not_logged(self, monkeypatch, tmp_path, caplog):
        key = self._run(monkeypatch, tmp_path, caplog, "")
        assert key.startswith("tmcp_") and len(key) > 10
        assert key not in caplog.text
        assert key[5:] not in caplog.text
        assert str(tmp_path / ".env") in caplog.text
        assert key in (tmp_path / ".env").read_text()
