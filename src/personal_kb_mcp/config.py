from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["debug", "info", "warning", "error"]
AuthMode = Literal["bearer"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    host: str = "127.0.0.1"
    port: int = Field(default=9999, ge=1, le=65535)
    mcp_path: str = "/mcp"
    log_level: LogLevel = "info"

    vault_path: Path = Path("./vault")
    state_db: Path = Path("./state/personal-kb.sqlite3")
    max_note_bytes: int = Field(default=102_400, gt=0)

    auth_mode: AuthMode = "bearer"
    api_key: SecretStr | None = None

    enable_writes: bool = True
    enable_move: bool = True
    enable_archive: bool = True
    enable_hard_delete: bool = False
    require_if_hash_for_updates: bool = True
    require_provenance: bool = True

    vector_enabled: bool = False
    vector_provider: str = "none"
    vector_collection: str = "personal_kb"
    vector_url: str | None = None
    embedding_provider: str = "none"
    embedding_model: str | None = None

    model_config = SettingsConfigDict(env_prefix="KB_", env_file=".env", extra="ignore")
