"""Tests for configuration module."""

import json
from unittest import mock


class TestWriteEnvVar:
    """Test _write_env_var helper."""

    def test_creates_new_file(self, tmp_path):
        from things_mcp.config import _write_env_var

        env_file = tmp_path / ".env"
        assert _write_env_var(env_file, "MY_KEY", "my_value")
        assert env_file.read_text() == "MY_KEY=my_value\n"
        assert env_file.stat().st_mode & 0o777 == 0o600

    def test_updates_existing_key(self, tmp_path):
        from things_mcp.config import _write_env_var

        env_file = tmp_path / ".env"
        env_file.write_text("MY_KEY=old_value\nOTHER=keep\n")
        assert _write_env_var(env_file, "MY_KEY", "new_value")
        content = env_file.read_text()
        assert "MY_KEY=new_value" in content
        assert "OTHER=keep" in content
        assert "old_value" not in content

    def test_appends_new_key(self, tmp_path):
        from things_mcp.config import _write_env_var

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value\n")
        assert _write_env_var(env_file, "NEW_KEY", "new_value")
        content = env_file.read_text()
        assert "EXISTING=value" in content
        assert "NEW_KEY=new_value" in content

    def test_handles_file_without_trailing_newline(self, tmp_path):
        from things_mcp.config import _write_env_var

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value")
        assert _write_env_var(env_file, "NEW_KEY", "new_value")
        content = env_file.read_text()
        assert "NEW_KEY=new_value" in content


class TestLegacyConfig:
    """Test legacy config file operations."""

    def test_load_missing_file(self):
        from things_mcp.config import _load_legacy_config

        with mock.patch("things_mcp.config.CONFIG_FILE") as mock_file:
            mock_file.exists.return_value = False
            assert _load_legacy_config() == {}

    def test_load_valid_config(self, tmp_path):
        from things_mcp.config import _load_legacy_config

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"things_auth_token": "test123"}))
        with mock.patch("things_mcp.config.CONFIG_FILE", config_file):
            result = _load_legacy_config()
            assert result["things_auth_token"] == "test123"

    def test_load_corrupt_file(self, tmp_path):
        from things_mcp.config import _load_legacy_config

        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json{{{")
        with mock.patch("things_mcp.config.CONFIG_FILE", config_file):
            assert _load_legacy_config() == {}

    def test_save_sets_permissions(self, tmp_path):
        from things_mcp.config import _save_legacy_config

        config_dir = tmp_path / ".things-mcp"
        config_file = config_dir / "config.json"
        with (
            mock.patch("things_mcp.config.CONFIG_DIR", config_dir),
            mock.patch("things_mcp.config.CONFIG_FILE", config_file),
        ):
            assert _save_legacy_config({"key": "value"})
            assert config_dir.stat().st_mode & 0o777 == 0o700
            assert config_file.stat().st_mode & 0o777 == 0o600


class TestGetThingsAuthToken:
    """Test token resolution priority."""

    def test_prefers_env_over_legacy(self, monkeypatch):
        from things_mcp.config import get_things_auth_token

        monkeypatch.setattr(
            "things_mcp.config.get_settings",
            lambda: mock.Mock(has_auth_token=True, things_auth_token="env-token"),
        )
        assert get_things_auth_token() == "env-token"

    def test_falls_back_to_legacy(self, monkeypatch, tmp_path):
        from things_mcp.config import get_things_auth_token

        monkeypatch.setattr(
            "things_mcp.config.get_settings",
            lambda: mock.Mock(has_auth_token=False),
        )
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"things_auth_token": "legacy-token"}))
        monkeypatch.setattr("things_mcp.config.CONFIG_FILE", config_file)
        assert get_things_auth_token() == "legacy-token"

    def test_returns_empty_when_none_configured(self, monkeypatch):
        from things_mcp.config import get_things_auth_token

        monkeypatch.setattr(
            "things_mcp.config.get_settings",
            lambda: mock.Mock(has_auth_token=False),
        )
        monkeypatch.setattr("things_mcp.config._load_legacy_config", lambda: {})
        assert get_things_auth_token() == ""


class TestEnforceFilePermissions:
    """Test startup permission enforcement."""

    def test_fixes_insecure_env_file(self, tmp_path, monkeypatch):
        from things_mcp.config import enforce_file_permissions

        env_file = tmp_path / ".env"
        env_file.write_text("SECRET=value\n")
        env_file.chmod(0o644)

        monkeypatch.setattr("things_mcp.config._find_env_file", lambda: env_file)
        monkeypatch.setattr("things_mcp.config.CONFIG_FILE", tmp_path / "nonexistent")
        monkeypatch.setattr(
            "things_mcp.config.CONFIG_DIR", tmp_path / "nonexistent_dir"
        )

        enforce_file_permissions()
        assert env_file.stat().st_mode & 0o777 == 0o600

    def test_fixes_insecure_config_dir(self, tmp_path, monkeypatch):
        from things_mcp.config import enforce_file_permissions

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_dir.chmod(0o755)

        monkeypatch.setattr(
            "things_mcp.config._find_env_file", lambda: tmp_path / "nope"
        )
        monkeypatch.setattr("things_mcp.config.CONFIG_FILE", tmp_path / "nonexistent")
        monkeypatch.setattr("things_mcp.config.CONFIG_DIR", config_dir)

        enforce_file_permissions()
        assert config_dir.stat().st_mode & 0o777 == 0o700

    def test_skips_nonexistent_files(self, tmp_path, monkeypatch):
        from things_mcp.config import enforce_file_permissions

        monkeypatch.setattr(
            "things_mcp.config._find_env_file", lambda: tmp_path / "nope"
        )
        monkeypatch.setattr("things_mcp.config.CONFIG_FILE", tmp_path / "nope2")
        monkeypatch.setattr("things_mcp.config.CONFIG_DIR", tmp_path / "nope3")
        # Should not raise
        enforce_file_permissions()
