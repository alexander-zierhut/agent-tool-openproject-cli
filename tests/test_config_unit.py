"""Unit tests for config load/save/resolve (no network)."""

from __future__ import annotations

import pytest

from opcli.config import Config, Profile, config_path
from agentcli.errors import ConfigError


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPCLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("OPCLI_PROFILE", raising=False)
    monkeypatch.delenv("OPCLI_BASE_URL", raising=False)
    yield


def test_roundtrip():
    cfg = Config()
    cfg.upsert_profile(Profile(name="prod", base_url="https://op.example.com", username="admin"))
    cfg.default_format = "table"
    cfg.save()
    assert config_path().exists()

    reloaded = Config.load()
    assert reloaded.current_profile == "prod"
    assert reloaded.default_format == "table"
    assert reloaded.profiles["prod"].base_url == "https://op.example.com"
    assert reloaded.profiles["prod"].username == "admin"


def test_empty_when_no_file():
    cfg = Config.load()
    assert cfg.profiles == {}
    assert cfg.default_format is None


def test_resolve_uses_env_base_url(monkeypatch):
    monkeypatch.setenv("OPCLI_BASE_URL", "http://localhost:8090")
    prof = Config.load().resolve()
    assert prof.base_url == "http://localhost:8090"


def test_resolve_env_overrides_profile(monkeypatch):
    cfg = Config()
    cfg.upsert_profile(Profile(name="default", base_url="https://saved.example.com"))
    cfg.save()
    monkeypatch.setenv("OPCLI_BASE_URL", "http://override:8090")
    assert Config.load().resolve().base_url == "http://override:8090"


def test_resolve_raises_without_config():
    with pytest.raises(ConfigError):
        Config.load().resolve()


def test_active_profile_honors_env(monkeypatch):
    monkeypatch.setenv("OPCLI_PROFILE", "staging")
    assert Config().active_profile_name() == "staging"


def test_malformed_config_raises():
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json")
    with pytest.raises(ConfigError):
        Config.load()


def test_profile_api_root():
    p = Profile(name="x", base_url="https://op.example.com/")
    assert p.api_root() == "https://op.example.com/api/v3"
