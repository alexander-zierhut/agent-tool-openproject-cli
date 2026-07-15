"""Unit tests for credential storage (env, keyring, file fallback)."""

from __future__ import annotations

import stat

import pytest

from opcli import credentials


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("OPCLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("OPCLI_TOKEN", raising=False)
    yield


def test_env_token_takes_precedence(monkeypatch):
    monkeypatch.setenv("OPCLI_TOKEN", "env-tok")
    assert credentials.get_token("default") == "env-tok"
    assert "environment variable" in credentials.backend_name()


def test_file_fallback_roundtrip(monkeypatch):
    # force the "no keyring" path
    monkeypatch.setattr(credentials, "_keyring_available", lambda: False)
    backend = credentials.store_token("default", "secret-abc")
    assert backend == "file"
    assert credentials.get_token("default") == "secret-abc"


def test_file_fallback_is_0600(monkeypatch, tmp_path):
    monkeypatch.setattr(credentials, "_keyring_available", lambda: False)
    credentials.store_token("default", "secret-abc")
    path = tmp_path / "credentials.json"
    assert path.exists()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_file_fallback_delete(monkeypatch):
    monkeypatch.setattr(credentials, "_keyring_available", lambda: False)
    credentials.store_token("p1", "tok1")
    credentials.store_token("p2", "tok2")
    credentials.delete_token("p1")
    assert credentials.get_token("p1") is None
    assert credentials.get_token("p2") == "tok2"


def test_backend_name_reports_fallback(monkeypatch):
    monkeypatch.setattr(credentials, "_keyring_available", lambda: False)
    assert "plaintext fallback file" in credentials.backend_name()


def test_get_token_missing_returns_none(monkeypatch):
    monkeypatch.setattr(credentials, "_keyring_available", lambda: False)
    assert credentials.get_token("never-stored") is None
