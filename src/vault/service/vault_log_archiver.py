from pathlib import Path

from pydantic import Field

from common.model import FrozenModel
from vault.service.vault_log_service import LogEntry, VaultLogService
from vault.service.vault_operational_paths import LOG_NOTE_PATH, log_archive_path


class LogFileContent(FrozenModel):
    """log 갱신으로 쓰게 되는 파일 하나의 절대 경로와 최종 본문."""

    path: Path
    content: str


class VaultLogArchiver(FrozenModel):
    """log.md에 changelog 항목을 쌓고, 지난 연도 항목은 log-YYYY.md로 분리합니다.

    provenance trailer는 호출 서비스마다 operation 이름이 달라 여기서 붙이지 않고,
    쓸 내용만 돌려줍니다. 호출자는 반환된 파일을 모두 persist해야 rotation이 완결됩니다.
    """

    vault_root: Path
    log_service: VaultLogService = Field(default_factory=VaultLogService)

    def append_entries(self, entries: list[LogEntry]) -> list[LogFileContent]:
        if not entries:
            return []

        appended = self.log_service.append_entry(self._read(self._log_path), entries[0])
        for entry in entries[1:]:
            appended = self.log_service.append_entry(appended, entry)
        rotation = self.log_service.rotate_by_year(
            appended,
            existing_archives=self._existing_archives(),
            timestamp=entries[-1].updated,
        )
        return [
            LogFileContent(path=self._log_path, content=rotation.log),
            *(
                LogFileContent(path=self.vault_root / archive.path, content=archive.content)
                for archive in rotation.archives
            ),
        ]

    def rotation_paths(self, entry_years: list[str]) -> list[Path]:
        """이번 갱신이 건드릴 수 있는 log 파일 경로 — write transaction snapshot 대상입니다.

        rotation은 log.md에 이미 있는 연도와 이번에 쌓을 항목의 연도 중 최신 연도를 제외한
        나머지를 archive로 옮기므로, 두 연도 집합을 합치면 후보가 모두 덮입니다.
        """
        existing_log = self._read(self._log_path)
        years = set(entry_years)
        if existing_log is not None:
            years.update(self.log_service.entry_years(existing_log))
        return [
            self._log_path,
            *(self.vault_root / log_archive_path(year) for year in sorted(years)),
        ]

    @property
    def _log_path(self) -> Path:
        return self.vault_root / LOG_NOTE_PATH

    def _existing_archives(self) -> dict[str, str]:
        archives: dict[str, str] = {}
        for archive_path in self.vault_root.glob("log-*.md"):
            content = self._read(archive_path)
            if content is not None:
                archives[archive_path.name] = content
        return archives

    def _read(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.exists() else None
