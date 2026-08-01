from vault.service.vault_log_service import (
    LogEntry,
    LogRotation,
    VaultLogService,
    WriteAction,
)


def _entry(
    *,
    date: str = "2026-06-12",
    action: WriteAction = "create",
    slug: str = "concepts/foo",
    path: str = "concepts/foo.md",
    description: str = "Foo summary",
    updated: str = "2026-06-12T10:31:46Z",
) -> LogEntry:
    return LogEntry(
        date=date,
        action=action,
        slug=slug,
        path=path,
        description=description,
        updated=updated,
    )


def test_log_service는_없으면_skeleton에_첫_entry를_쌓는다() -> None:
    # When: 기존 log가 없을 때 첫 entry를 append한다.
    result = VaultLogService().append_entry(None, _entry())

    # Then: Wiki Log skeleton과 함께 entry가 만들어지고 provenance는 붙지 않는다.
    assert result.startswith("---\ntitle: Wiki Log\n")
    assert 'created: "2026-06-12T10:31:46Z"' in result
    assert "# Wiki Log" in result
    assert "> Append-only changelog of wiki writes. Newest entries at top." in result
    assert "## [2026-06-12] create | concepts/foo" in result
    assert "- Created: `concepts/foo.md` — Foo summary" in result
    assert "kb-provenance" not in result


def test_log_service는_새_entry를_맨_위에_쌓고_updated를_갱신한다() -> None:
    # Given: 이미 한 건이 기록된 log가 있다.
    first = VaultLogService().append_entry(
        None, _entry(slug="concepts/old", path="concepts/old.md", description="Old")
    )

    # When: 더 최신 entry를 append한다.
    second = VaultLogService().append_entry(
        first,
        _entry(
            date="2026-06-13",
            action="update",
            slug="concepts/new",
            path="concepts/new.md",
            description="New",
            updated="2026-06-13T00:00:00Z",
        ),
    )

    # Then: 최신 entry가 위에 오고 update 라벨/updated frontmatter가 반영되며 과거 entry는 유지된다.
    assert second.index("concepts/new") < second.index("concepts/old")
    assert "## [2026-06-13] update | concepts/new" in second
    assert "- Updated: `concepts/new.md` — New" in second
    assert 'updated: "2026-06-13T00:00:00Z"' in second
    assert "## [2026-06-12] create | concepts/old" in second


def test_log_service는_heading과_intro를_중복으로_쌓지_않는다() -> None:
    # When: 같은 log에 두 번 append한다.
    first = VaultLogService().append_entry(None, _entry(slug="concepts/a", path="concepts/a.md"))
    second = VaultLogService().append_entry(first, _entry(slug="concepts/b", path="concepts/b.md"))

    # Then: Wiki Log 제목과 intro는 한 번씩만 존재한다.
    assert second.count("# Wiki Log") == 1
    assert second.count("Newest entries at top.") == 1


def test_log_service는_delete_entry를_쌓는다() -> None:
    # When: 삭제 entry를 append한다.
    result = VaultLogService().append_entry(None, _entry(action="delete"))

    # Then: delete action과 삭제 라벨이 log block에 기록된다.
    assert "## [2026-06-12] delete | concepts/foo" in result
    assert "- Deleted: `concepts/foo.md` — Foo summary" in result


def _rotated(log_content: str, *, archives: dict[str, str] | None = None) -> LogRotation:
    return VaultLogService().rotate_by_year(
        log_content,
        existing_archives=archives or {},
        timestamp="2027-01-04T00:00:00Z",
    )


def test_log_service는_연도가_넘어가면_지난_연도를_archive로_분리한다() -> None:
    # Given: 2026년 항목이 쌓인 log에 2027년 항목이 추가됐다.
    log = VaultLogService().append_entry(
        None, _entry(slug="concepts/old", path="concepts/old.md", description="Old")
    )
    log = VaultLogService().append_entry(
        log,
        _entry(
            date="2027-01-04",
            slug="concepts/new",
            path="concepts/new.md",
            description="New",
            updated="2027-01-04T00:00:00Z",
        ),
    )

    # When: 연도 rotation을 적용한다.
    rotation = _rotated(log)

    # Then: log.md에는 최신 연도만 남고 지난 연도는 log-2026.md로 옮겨진다.
    assert "## [2027-01-04] create | concepts/new" in rotation.log
    assert "concepts/old" not in rotation.log
    assert "> Archived: [[log-2026]]" in rotation.log
    assert [archive.path for archive in rotation.archives] == ["log-2026.md"]
    archive_content = rotation.archives[0].content
    assert archive_content.startswith("---\ntitle: Wiki Log 2026\n")
    assert "type: log" in archive_content
    assert "# Wiki Log 2026" in archive_content
    assert "archived from [[log]]" in archive_content
    assert "## [2026-06-12] create | concepts/old" in archive_content
    assert "- Created: `concepts/old.md` — Old" in archive_content


def test_log_service는_같은_연도만_있으면_rotation하지_않는다() -> None:
    # Given: 같은 해 항목만 쌓인 log가 있다.
    log = VaultLogService().append_entry(None, _entry(slug="concepts/a", path="concepts/a.md"))
    log = VaultLogService().append_entry(log, _entry(slug="concepts/b", path="concepts/b.md"))

    # When: 연도 rotation을 적용한다.
    rotation = _rotated(log)

    # Then: log 내용은 그대로이고 archive도 생기지 않는다.
    assert rotation.log == log
    assert rotation.archives == []


def test_log_service는_기존_archive에_항목을_합치고_최신순을_유지한다() -> None:
    # Given: 2026년 archive가 이미 있고, log에 뒤늦은 2026년 항목이 남아 있다.
    first_rotation = _rotated(
        VaultLogService().append_entry(
            VaultLogService().append_entry(
                None,
                _entry(
                    date="2026-01-05",
                    slug="concepts/jan",
                    path="concepts/jan.md",
                    description="Jan",
                    updated="2026-01-05T00:00:00Z",
                ),
            ),
            _entry(
                date="2027-01-04",
                slug="concepts/new",
                path="concepts/new.md",
                description="New",
                updated="2027-01-04T00:00:00Z",
            ),
        )
    )
    existing_archive = first_rotation.archives[0].content
    log_with_late_entry = VaultLogService().append_entry(
        first_rotation.log,
        _entry(
            date="2026-12-31",
            slug="concepts/dec",
            path="concepts/dec.md",
            description="Dec",
            updated="2026-12-31T00:00:00Z",
        ),
    )

    # When: 기존 archive를 넘겨 다시 rotation한다.
    rotation = _rotated(log_with_late_entry, archives={"log-2026.md": existing_archive})

    # Then: 두 항목이 한 archive에 합쳐지고 최신 항목이 위에 온다.
    archive_content = rotation.archives[0].content
    assert archive_content.index("concepts/dec") < archive_content.index("concepts/jan")
    assert archive_content.count("# Wiki Log 2026") == 1
    assert "> Archived: [[log-2026]]" in rotation.log
    assert rotation.log.count("> Archived:") == 1


def test_log_service는_날짜를_읽을_수_없는_항목이_있으면_rotation을_건너뛴다() -> None:
    # Given: 손으로 편집돼 날짜가 없는 항목이 섞인 log가 있다.
    log = VaultLogService().append_entry(
        None,
        _entry(
            date="2027-01-04",
            slug="concepts/new",
            path="concepts/new.md",
            description="New",
            updated="2027-01-04T00:00:00Z",
        ),
    )
    hand_edited = log.replace(
        "## [2027-01-04] create | concepts/new",
        "## [메모] 손으로 남긴 항목\n\n## [2027-01-04] create | concepts/new",
    )

    # When: 연도 rotation을 적용한다.
    rotation = _rotated(hand_edited)

    # Then: 잘라내지 않고 그대로 둔다.
    assert rotation.log == hand_edited
    assert rotation.archives == []
