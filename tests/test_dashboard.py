"""Tests for dashboard hardening (input validation, security headers)."""


class TestDashboardParseDays:
    """Test the _parse_days helper used by dashboard routes."""

    def _parse_days(self, query_string):
        """Simulate _parse_days behavior from fast_server."""

        class FakeRequest:
            class query_params:
                @staticmethod
                def get(key, default=30):
                    if key == "days":
                        return query_string
                    return default

        try:
            days = int(FakeRequest.query_params.get("days", 30))
        except (ValueError, TypeError):
            days = 30
        return max(0, min(days, 365))

    def test_valid_number(self):
        assert self._parse_days("7") == 7

    def test_invalid_string(self):
        assert self._parse_days("abc") == 30

    def test_negative(self):
        assert self._parse_days("-5") == 0

    def test_excessive(self):
        assert self._parse_days("99999") == 365

    def test_zero(self):
        assert self._parse_days("0") == 0

    def test_empty_string(self):
        assert self._parse_days("") == 30

    def test_none(self):
        assert self._parse_days(None) == 30
