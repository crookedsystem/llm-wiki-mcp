from vault.service.vault_log_service import LogEntry, VaultLogService, WriteAction


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
