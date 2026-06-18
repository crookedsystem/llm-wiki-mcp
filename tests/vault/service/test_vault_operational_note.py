from vault.service.vault_operational_note import OperationalNote

_SOURCE = (
    "---\n"
    "title: Wiki Log\n"
    'created: "2026-06-01T00:00:00Z"\n'
    'updated: "2026-06-01T00:00:00Z"\n'
    "type: log\n"
    "---\n"
    "\n"
    "# Wiki Log\n"
    "\n"
    "> intro\n"
)
_WRITTEN = _SOURCE + "<!-- kb-provenance: source_hash=abc; operation=write_note; actor=tester -->\n"


def test_parse는_provenance를_떼고_frontmatter와_body로_나눈다() -> None:
    # When: provenance trailer가 붙은 운영 파일을 parse한다.
    note = OperationalNote.parse(_WRITTEN)

    # Then: frontmatter/body가 분리되고 trailer는 제거된다.
    assert note.frontmatter == (
        "title: Wiki Log\n"
        'created: "2026-06-01T00:00:00Z"\n'
        'updated: "2026-06-01T00:00:00Z"\n'
        "type: log"
    )
    assert note.body == "\n# Wiki Log\n\n> intro\n"
    assert "kb-provenance" not in note.render()


def test_render는_parse의_역연산이다() -> None:
    # When/Then: parse 후 render하면 provenance 없는 원본 source로 정확히 복원된다.
    assert OperationalNote.parse(_WRITTEN).render() == _SOURCE


def test_with_updated는_updated_줄만_바꾼다() -> None:
    # Given: 기존 운영 파일을 parse한 노트가 있다.
    note = OperationalNote.parse(_WRITTEN)

    # When: updated timestamp를 새로 지정한다.
    bumped = note.with_updated("2026-06-18T12:00:00Z")

    # Then: updated 줄만 교체되고 created/body는 그대로다.
    assert bumped.render() == _SOURCE.replace(
        'updated: "2026-06-01T00:00:00Z"',
        'updated: "2026-06-18T12:00:00Z"',
    )
    assert bumped.body == note.body


def test_with_body는_frontmatter를_보존한다() -> None:
    # When: body만 교체한다.
    replaced = OperationalNote.parse(_WRITTEN).with_body("\n# Wiki Log\n\nnew body\n")

    # Then: frontmatter는 유지되고 body만 바뀐다.
    assert replaced.frontmatter.startswith("title: Wiki Log")
    assert replaced.render().endswith("\n# Wiki Log\n\nnew body\n")


def test_frontmatter가_없으면_본문_그대로_다룬다() -> None:
    # When: frontmatter가 없는 내용을 parse/render한다.
    note = OperationalNote.parse("# Heading\n\nbody\n")

    # Then: body만 보존하고 with_updated는 무의미한 변경을 만들지 않는다.
    assert note.frontmatter == ""
    assert note.render() == "# Heading\n\nbody\n"
    assert note.with_updated("2026-06-18T12:00:00Z").render() == "# Heading\n\nbody\n"
