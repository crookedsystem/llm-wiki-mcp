from pathlib import Path

from vault.service.vault_log_archiver import VaultLogArchiver
from vault.service.vault_log_service import LogEntry, VaultLogService


def _entry(
    *,
    date: str = "2026-06-12",
    slug: str = "concepts/old",
    path: str = "concepts/old.md",
    description: str = "Old summary",
    updated: str = "2026-06-12T10:31:46Z",
) -> LogEntry:
    return LogEntry(
        date=date,
        action="create",
        slug=slug,
        path=path,
        description=description,
        updated=updated,
    )


def _vault_with_last_year_log(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "log.md").write_text(
        VaultLogService().append_entry(None, _entry()),
        encoding="utf-8",
    )
    return vault


def test_log_archiver는_rotation_시_archive를_log보다_먼저_쓰도록_돌려준다(
    tmp_path: Path,
) -> None:
    # Given: 2026년 항목만 있는 log.md가 있다.
    vault = _vault_with_last_year_log(tmp_path)
    archiver = VaultLogArchiver(vault_root=vault)

    # When: 연도가 넘어가는 2027년 항목을 쌓는다.
    log_files = archiver.append_entries(
        [
            _entry(
                date="2027-01-04",
                slug="concepts/new",
                path="concepts/new.md",
                description="New summary",
                updated="2027-01-04T00:00:00Z",
            )
        ]
    )

    # Then: archive가 앞, log.md가 마지막이다. 반대 순서면 log.md가 잘린 뒤 archive가
    # 써지기 전에 죽었을 때 지난 연도 히스토리가 통째로 사라진다.
    assert [log_file.path.name for log_file in log_files] == ["log-2026.md", "log.md"]
    assert "concepts/old" in log_files[0].content
    assert "concepts/old" not in log_files[-1].content


def test_log_archiver는_rotation이_없으면_log만_돌려준다(tmp_path: Path) -> None:
    # Given: 2026년 항목만 있는 log.md가 있다.
    vault = _vault_with_last_year_log(tmp_path)
    archiver = VaultLogArchiver(vault_root=vault)

    # When: 같은 연도 항목을 쌓는다.
    log_files = archiver.append_entries(
        [_entry(date="2026-06-13", slug="concepts/same", path="concepts/same.md")]
    )

    # Then: archive 없이 log.md 한 개만 나온다.
    assert [log_file.path.name for log_file in log_files] == ["log.md"]
