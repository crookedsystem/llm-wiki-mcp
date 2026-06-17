from pathlib import Path

from pydantic import Field

from common.model import FrozenModel

DEFAULT_DENIED_NAMES = frozenset({".git", ".obsidian", "node_modules", ".trash"})


class VaultPathError(ValueError):
    """Raised when a requested vault path is unsafe or unsupported."""


class VaultPaths(FrozenModel):
    """Resolve user-provided note paths while keeping every path inside the vault."""

    root: Path
    denied_names: frozenset[str] = Field(default_factory=lambda: DEFAULT_DENIED_NAMES)

    def resolve_note_path(self, note_path: str | Path) -> Path:
        relative_path = Path(note_path)
        if relative_path.suffix != ".md":
            raise VaultPathError("Only markdown note paths are supported")
        return self.resolve_file_path(relative_path)

    def resolve_file_path(self, file_path: str | Path) -> Path:
        relative_path = Path(file_path)
        if relative_path.is_absolute():
            raise VaultPathError("Path must be relative to the vault")
        vault_root = self.root.resolve()
        resolved_path = (vault_root / relative_path).resolve()
        self._ensure_inside_vault(vault_root, resolved_path)
        self._ensure_allowed_parts(vault_root, resolved_path)
        return resolved_path

    def _ensure_inside_vault(self, vault_root: Path, resolved_path: Path) -> None:
        try:
            resolved_path.relative_to(vault_root)
        except ValueError as error:
            raise VaultPathError(f"Path escapes outside vault: {resolved_path}") from error

    def _ensure_allowed_parts(self, vault_root: Path, resolved_path: Path) -> None:
        relative_parts = resolved_path.relative_to(vault_root).parts
        denied_part = next((part for part in relative_parts if part in self.denied_names), None)
        if denied_part is not None:
            raise VaultPathError(f"Path uses denied vault directory: {denied_part}")
