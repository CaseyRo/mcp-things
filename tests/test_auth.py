"""Tests for bearer token authentication."""

import pytest

from things_mcp.auth import BearerTokenVerifier, generate_api_key


class TestGenerateApiKey:
    def test_format(self):
        key = generate_api_key()
        assert key.startswith("tmcp_")
        assert len(key) > 20

    def test_unique(self):
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10


class TestBearerTokenVerifier:
    @pytest.fixture
    def verifier(self):
        return BearerTokenVerifier("tmcp_test_key_12345")

    @pytest.mark.asyncio
    async def test_valid_token(self, verifier):
        result = await verifier.verify_token("tmcp_test_key_12345")
        assert result is not None
        assert result.client_id == "things-mcp-client"
        assert result.scopes == ["all"]

    @pytest.mark.asyncio
    async def test_invalid_token(self, verifier):
        result = await verifier.verify_token("wrong_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_token(self, verifier):
        result = await verifier.verify_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_timing_safe(self, verifier):
        """Verify we use hmac.compare_digest (constant-time)."""
        import things_mcp.auth as auth_module
        import inspect

        source = inspect.getsource(auth_module.BearerTokenVerifier.verify_token)
        assert "hmac.compare_digest" in source
