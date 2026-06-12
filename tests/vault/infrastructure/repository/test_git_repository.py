import asyncio
import subprocess
from datetime import date
from pathlib import Path

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_path import VaultPaths
from vault.infrastructure.repository.git_repository import GitRepository
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_write_service import VaultWriteService


def test_git_repository가_연결된_note_작성은_commit_hash를_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: git repository로 초기화된 vault와 git repository adapter가 있다.
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
        writer = VaultWriteService(
            paths=VaultPaths(root=vault_root),
            queue=VaultWriteQueue(),
            actor="tester",
            git_repository=GitRepository(root=vault_root),
        )

        # When: note를 작성한다.
        result = await writer.write_note(
            WriteNoteCommand(
                note_path="concepts/today.md",
                title="Today",
                type="concept",
                tags=("git",),
                sources=("raw/articles/source.md",),
                body="## Summary\nBody text",
                created=date(2026, 6, 12),
                updated=date(2026, 6, 12),
            )
        )

        # Then: 작성된 note는 git commit에 포함되고 40자리 commit hash가 반환된다.
        assert result.commit_hash is not None
        assert len(result.commit_hash) == 40
        assert _git_stdout(vault_root, "rev-parse", "HEAD") == result.commit_hash
        assert "concepts/today.md" in _git_stdout(
            vault_root,
            "show",
            "--name-only",
            "--format=",
            result.commit_hash,
        )

    asyncio.run(exercise_writer())


def _git_stdout(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
