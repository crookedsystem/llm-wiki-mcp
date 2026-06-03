from pathlib import Path

from pytest import MonkeyPatch

from personal_kb_mcp.config import Settings


def test_settings_use_safe_defaults(tmp_path: Path) -> None:
    settings = Settings(vault_path=tmp_path / "vault")

    assert settings.host == "127.0.0.1"
    assert settings.port == 9999
    assert settings.mcp_path == "/mcp"
    assert settings.enable_writes is True
    assert settings.require_if_hash_for_updates is True
    assert settings.require_provenance is True
    assert settings.vector_enabled is False
    assert settings.vector_provider == "none"


def test_settings_read_environment_overrides(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KB_PORT", "10000")
    monkeypatch.setenv("KB_VAULT_PATH", str(tmp_path / "env-vault"))
    monkeypatch.setenv("KB_VECTOR_PROVIDER", "qdrant")

    settings = Settings()

    assert settings.port == 10000
    assert settings.vault_path == tmp_path / "env-vault"
    assert settings.vector_provider == "qdrant"
