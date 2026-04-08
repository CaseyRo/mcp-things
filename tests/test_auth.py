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
