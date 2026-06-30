from vault.service.vault_index_service import IndexEntry, VaultIndexService


def _entry(
    *,
    slug: str = "concepts/foo",
    title: str = "Foo",
    summary: str | None = "Foo summary",
    section: str = "Concepts",
    updated: str = "2026-06-12T10:31:46Z",
) -> IndexEntry:
    return IndexEntry(slug=slug, title=title, summary=summary, section=section, updated=updated)


def test_index_service는_없으면_skeleton에_섹션과_entry를_만든다() -> None:
    # When: 기존 index가 없을 때 첫 entry를 upsert한다.
    result = VaultIndexService().upsert_entry(None, _entry())

    # Then: Wiki Index skeleton, 섹션, 항목이 만들어지고 provenance는 붙지 않는다.
    assert result.startswith("---\ntitle: Wiki Index\n")
    assert "# Wiki Index" in result
    assert "## Concepts" in result
    assert "- [[concepts/foo|Foo]] — Foo summary" in result
    assert "kb-provenance" not in result


def test_index_service는_summary가_없으면_제목만_링크한다() -> None:
    # When: summary 없이 upsert한다.
    result = VaultIndexService().upsert_entry(None, _entry(summary=None))

    # Then: em-dash 설명 없이 wikilink만 남는다.
    entry_line = next(
        line for line in result.splitlines() if line.startswith("- [[concepts/foo|Foo]]")
    )
    assert entry_line == "- [[concepts/foo|Foo]]"


def test_index_service는_같은_slug를_제자리에서_갱신한다() -> None:
    # Given: 한 항목이 등재된 index가 있다.
    first = VaultIndexService().upsert_entry(None, _entry(title="Old Title", summary="Old summary"))

    # When: 같은 slug를 새 제목/설명으로 다시 upsert한다.
    second = VaultIndexService().upsert_entry(
        first, _entry(title="New Title", summary="New summary")
    )

    # Then: 중복 없이 제자리에서 갱신된다.
    assert second.count("[[concepts/foo|") == 1
    assert "- [[concepts/foo|New Title]] — New summary" in second
    assert "Old Title" not in second
    assert "Old summary" not in second


def test_index_service는_summary_없이_갱신하면_기존_설명을_보존한다() -> None:
    # Given: 설명이 달린 항목이 등재된 index가 있다.
    first = VaultIndexService().upsert_entry(None, _entry(title="Foo", summary="원래 설명"))

    # When: summary 없이(제목만 바꿔) 같은 slug를 갱신한다.
    second = VaultIndexService().upsert_entry(first, _entry(title="Foo Renamed", summary=None))

    # Then: 제목은 갱신되지만 기존 설명은 사라지지 않고 보존된다.
    assert "- [[concepts/foo|Foo Renamed]] — 원래 설명" in second
    assert second.count("[[concepts/foo|") == 1


def test_index_service는_새_summary가_있으면_기존_설명을_교체한다() -> None:
    # Given: 설명이 있는 항목이 있다.
    first = VaultIndexService().upsert_entry(None, _entry(summary="old summary"))

    # When: 새 summary로 갱신한다.
    second = VaultIndexService().upsert_entry(first, _entry(summary="new summary"))

    # Then: 명시된 새 summary가 기존 설명을 덮어쓴다.
    assert "- [[concepts/foo|Foo]] — new summary" in second
    assert "old summary" not in second


def test_index_service는_설명이_없던_항목은_summary_없는_갱신에도_제목만_유지한다() -> None:
    # Given: 설명 없이 등재된 항목이 있다.
    first = VaultIndexService().upsert_entry(None, _entry(summary=None))

    # When: summary 없이 다시 갱신한다.
    second = VaultIndexService().upsert_entry(first, _entry(summary=None))

    # Then: 보존할 설명이 없으므로 제목 링크만 유지된다(중복 없음).
    entry_line = next(
        line for line in second.splitlines() if line.startswith("- [[concepts/foo|Foo]]")
    )
    assert entry_line == "- [[concepts/foo|Foo]]"
    assert second.count("[[concepts/foo|") == 1


def test_index_service는_기존_섹션_끝에_항목을_추가한다() -> None:
    # Given: Concepts 섹션에 한 항목이 있다.
    first = VaultIndexService().upsert_entry(
        None, _entry(slug="concepts/a", title="A", summary="A desc")
    )

    # When: 같은 섹션에 다른 항목을 추가한다.
    second = VaultIndexService().upsert_entry(
        first, _entry(slug="concepts/b", title="B", summary="B desc")
    )

    # Then: 섹션은 하나로 유지되고 새 항목은 기존 항목 뒤에 온다.
    assert second.count("## Concepts") == 1
    assert second.index("concepts/a") < second.index("concepts/b")


def test_index_service는_없는_섹션을_새로_만든다() -> None:
    # Given: Concepts 섹션만 있는 index가 있다.
    concepts = VaultIndexService().upsert_entry(
        None, _entry(slug="concepts/a", title="A", summary="A desc")
    )

    # When: Entities 항목을 upsert한다.
    with_entity = VaultIndexService().upsert_entry(
        concepts,
        _entry(slug="entities/x", title="X", summary="X entity", section="Entities"),
    )

    # Then: 두 섹션이 공존한다.
    assert "## Concepts" in with_entity
    assert "## Entities" in with_entity
    assert "- [[entities/x|X]] — X entity" in with_entity


def test_index_service는_raw_노트를_raw_sources_섹션에_넣는다() -> None:
    # When: raw 노트를 Raw Sources 섹션으로 upsert한다.
    result = VaultIndexService().upsert_entry(
        None,
        _entry(
            slug="raw/transcripts/foo",
            title="Foo transcript",
            summary="원문 기록",
            section="Raw Sources",
        ),
    )

    # Then: Raw Sources 섹션에 항목이 들어간다.
    assert "## Raw Sources" in result
    assert "- [[raw/transcripts/foo|Foo transcript]] — 원문 기록" in result


def test_index_service는_설명_속_링크가_아니라_항목_앵커로_매칭한다() -> None:
    # Given: 설명에 concepts/a 링크를 품은 concepts/b 항목이 있다.
    base = VaultIndexService().upsert_entry(
        None,
        IndexEntry(
            slug="concepts/b",
            title="B",
            summary="relates to [[concepts/a|A]]",
            section="Concepts",
            updated="2026-06-12T10:31:46Z",
        ),
    )

    # When: concepts/a를 upsert한다.
    result = VaultIndexService().upsert_entry(
        base, _entry(slug="concepts/a", title="A", summary="A desc")
    )

    # Then: 설명 링크 때문에 b가 덮이지 않고 a는 별도 항목으로 추가된다.
    assert "- [[concepts/b|B]] — relates to [[concepts/a|A]]" in result
    assert "- [[concepts/a|A]] — A desc" in result
    assert result.count("## Concepts") == 1


def test_index_service는_항목_앵커가_일치하는_slug만_제거한다() -> None:
    # Given: concepts/a 항목과, 설명에 concepts/a를 언급하는 concepts/b 항목이 있다.
    first = VaultIndexService().upsert_entry(
        None,
        _entry(slug="concepts/a", title="A", summary="A desc"),
    )
    second = VaultIndexService().upsert_entry(
        first,
        IndexEntry(
            slug="concepts/b",
            title="B",
            summary="relates to [[concepts/a|A]]",
            section="Concepts",
            updated="2026-06-12T10:31:46Z",
        ),
    )

    # When: concepts/a 항목을 제거한다.
    result = VaultIndexService().remove_entry(
        second,
        slug="concepts/a",
        updated="2026-06-12T11:00:00Z",
    )

    # Then: 항목 anchor가 concepts/a인 줄만 제거되고 설명 속 링크는 건드리지 않는다.
    assert result is not None
    assert "- [[concepts/a|A]] — A desc" not in result
    assert "- [[concepts/b|B]] — relates to [[concepts/a|A]]" in result
    assert 'updated: "2026-06-12T11:00:00Z"' in result
