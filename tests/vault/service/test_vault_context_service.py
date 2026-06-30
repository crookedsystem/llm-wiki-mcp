from pathlib import Path

from vault.dto.response.context_response import ContextResponseMapper
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.context_command import ContextCommand
from vault.service.vault_context_service import VaultContextService


def _write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _context_service(vault_root: Path) -> VaultContextService:
    return VaultContextService(note_repository=VaultNoteRepository(root=vault_root))


def test_context는_깨진_link와_연결대상과_근거검색어를_반환한다(
    tmp_path: Path,
) -> None:
    # Given: orientation 파일, entity anchor, domain rule, 깨진 wikilink가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "SCHEMA.md",
        "---\n"
        "title: Wiki Schema\n"
        "type: schema\n"
        "tags: [llm-wiki]\n"
        "---\n\n"
        "# Wiki Schema\n\nlink rules\n",
    )
    _write_note(vault_root / "index.md", "# Wiki Index\n\nsample catalog\n")
    _write_note(vault_root / "log.md", "# Wiki Log\n\nrecent sample changes\n")
    _write_note(
        vault_root / "entities" / "sample-api.md",
        "---\n"
        "title: sample-api\n"
        "type: entity\n"
        "tags: [project-context, sample-api]\n"
        "---\n\n"
        "# sample-api\n\nsample chat service repository context\n",
    )
    _write_note(
        vault_root / "concepts" / "sample-chat-domain-rules.md",
        "---\n"
        "title: sample chat domain rules\n"
        "type: concept\n"
        "tags: [domain-rule, sample-api]\n"
        "---\n\n"
        "# sample chat domain rules\n\nsample chat secret room rule\n",
    )
    _write_note(
        vault_root / "queries" / "sample-chat.md",
        "---\n"
        "title: sample chat investigation\n"
        "type: query\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample chat investigation\n\nRelated: [[missing-room-rule]]\n",
    )

    # When: prewrite mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="sample chat domain", mode="prewrite", limit=10)
    )

    # Then: context는 snippet이 아닌 연결 작업용 최소 metadata를 반환한다.
    assert result.mode == "prewrite"
    assert [reference.path for reference in result.orientation] == [
        "SCHEMA.md",
        "index.md",
        "log.md",
    ]
    assert result.broken_links[0].source_path == "queries/sample-chat.md"
    assert result.broken_links[0].normalized_target == "missing-room-rule"
    assert result.broken_links[0].suggested_path == "concepts/missing-room-rule.md"
    assert result.broken_links[0].followup_search == "missing-room-rule"
    target_by_path = {target.path: target for target in result.link_targets}
    assert target_by_path["entities/sample-api.md"].relation == "entity_anchor"
    assert target_by_path["concepts/sample-chat-domain-rules.md"].relation == "domain_rule"
    assert all(target.followup_search for target in result.link_targets)
    assert any("kb_search_notes" in usage for usage in result.usage)
    assert any("stable link anchors" in criterion for criterion in result.entity_guidance.criteria)


def test_context는_이미_연결되지_않은_관련_note_link를_제안한다(tmp_path: Path) -> None:
    # Given: query note와 entity note가 같은 tag를 공유하지만 아직 wikilink로 연결되지 않았다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "entities" / "llm-wiki-mcp.md",
        "---\n"
        "title: llm-wiki-mcp\n"
        "type: entity\n"
        "tags: [llm-wiki-mcp]\n"
        "---\n\n"
        "# llm-wiki-mcp\n\ncontext graph tool\n",
    )
    _write_note(
        vault_root / "queries" / "context-tool.md",
        "---\n"
        "title: context tool design\n"
        "type: query\n"
        "tags: [llm-wiki-mcp]\n"
        "---\n\n"
        "# context tool design\n\ncontext graph tool should expose link candidates\n",
    )

    # When: prewrite mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="llm wiki mcp context graph", mode="prewrite", limit=5)
    )

    # Then: source hash와 target path를 포함한 연결 제안이 나온다.
    assert result.broken_links == []
    assert result.suggested_links
    suggestion = result.suggested_links[0]
    assert suggestion.source_path == "queries/context-tool.md"
    assert suggestion.target_path == "entities/llm-wiki-mcp.md"
    assert suggestion.relation == "add_link_to_entity_anchor"
    assert "shared tags" in suggestion.reason
    assert suggestion.source_content_hash
    assert suggestion.followup_search


def test_prompt_context는_깨진링크보다_직접_link_target을_우선한다(tmp_path: Path) -> None:
    # Given: broken link가 많은 vault에 query와 정확히 맞는 entity anchor가 있다.
    vault_root = tmp_path / "vault"
    _write_note(vault_root / "SCHEMA.md", "# Wiki Schema\n\nsample schema\n")
    _write_note(vault_root / "index.md", "# Wiki Index\n\nsample index\n")
    _write_note(vault_root / "log.md", "# Wiki Log\n\nsample log\n")
    _write_note(
        vault_root / "entities" / "sample-api.md",
        "---\n"
        "title: sample-api\n"
        "type: entity\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample-api\n\nsample api project context\n",
    )
    for index in range(10):
        _write_note(
            vault_root / "queries" / f"broken-{index}.md",
            f"# broken {index}\n\nRelated: [[missing-{index}]]\n",
        )

    # When: 작은 limit으로 prompt context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="sample api", mode="prompt", limit=3)
    )

    # Then: prompt mode는 formatter가 버릴 broken link보다 직접 target을 우선한다.
    assert [target.path for target in result.link_targets] == ["entities/sample-api.md"]


def test_prompt_context는_prompt_hints를_lane별_cue로_반환한다(tmp_path: Path) -> None:
    # Given: prompt hook이 바로 사용할 수 있는 Prompt hints section이 있다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "entities" / "kim-yongseok.md",
        "---\n"
        "title: 김용석 CTO\n"
        "type: entity\n"
        "tags: [communication]\n"
        "---\n\n"
        "# 김용석 CTO\n\n"
        "PR update communication context.\n\n"
        "## Prompt hints\n"
        "- lane: person_tone; applies when: writing a PR update; do: lead with risk; "
        "avoid: generic status narration; evidence: explicit review feedback; "
        "confidence: high; updated: 2026-06-30; scope: person:kim-yongseok.\n"
    )
    _write_note(
        vault_root / "entities" / "fanplus-api.md",
        "---\n"
        "title: fanplus-api\n"
        "type: entity\n"
        "tags: [project-context]\n"
        "---\n\n"
        "# fanplus-api\n\n"
        "API response contract context.\n\n"
        "## Prompt hints\n"
        "- lane: project_conventions; applies when: changing API response shape; "
        "check before acting: compare AS-IS and TO-BE JSON; confidence: medium.\n"
        "- kind: procedural_pattern; applies when: running API regression tests; "
        "do: reuse the existing pytest selector; evidence: repo test workflow; "
        "confidence: high.\n"
        "- lane: repeated_mistakes; applies when: changing API response shape; "
        "prevention cue: announce FE contract drift; confidence: high; "
        "review after: 2026-09-30.\n",
    )

    # When: prompt mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="김용석 fanplus-api PR API response", mode="prompt", limit=8)
    )
    response = ContextResponseMapper.to_response(result)

    # Then: prompt hints가 일반 memory_kind와 legacy lane schema 양쪽으로 전달된다.
    cues_by_kind = {cue.memory_kind: cue for cue in result.prompt_cues}
    assert set(cues_by_kind) == {
        "preference_profile",
        "project_convention",
        "procedural_pattern",
        "failure_prevention",
    }
    assert result.person_tone[0].path == "entities/kim-yongseok.md"
    assert result.person_tone[0].do == "lead with risk"
    assert result.person_tone[0].avoid == "generic status narration"
    assert result.project_conventions[0].check_before_acting == "compare AS-IS and TO-BE JSON"
    assert result.repeated_mistakes[0].prevention_cue == "announce FE contract drift"
    assert result.repeated_mistakes[0].review_after == "2026-09-30"
    response_by_kind = {cue["memory_kind"]: cue for cue in response["prompt_cues"]}
    assert response_by_kind["procedural_pattern"]["do"] == "reuse the existing pytest selector"
    assert response_by_kind["preference_profile"]["scope"] == "person:kim-yongseok"
    assert response["person_tone"][0]["evidence"] == "explicit review feedback"
    assert response["project_conventions"][0]["confidence"] == "medium"


def test_context는_기존_wikilink가_있으면_중복_연결을_제안하지_않는다(
    tmp_path: Path,
) -> None:
    # Given: query note가 이미 entity note를 wikilink로 참조한다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "entities" / "llm-wiki-mcp.md",
        "---\ntitle: llm-wiki-mcp\ntype: entity\ntags: [llm-wiki-mcp]\n---\n\n# llm-wiki-mcp\n",
    )
    _write_note(
        vault_root / "queries" / "context-tool.md",
        "---\n"
        "title: context tool design\n"
        "type: query\n"
        "tags: [llm-wiki-mcp]\n"
        "---\n\n"
        "# context tool design\n\nSee [[entities/llm-wiki-mcp]].\n",
    )

    # When: context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="llm wiki mcp context graph", mode="prewrite", limit=5)
    )

    # Then: 이미 존재하는 link는 중복 제안하지 않는다.
    assert result.suggested_links == []


def test_context는_path_prefix로_연결_source와_target을_좁히되_orientation은_유지한다(
    tmp_path: Path,
) -> None:
    # Given: orientation 파일과 entities 안의 target, concepts 안의 별도 note가 있다.
    vault_root = tmp_path / "vault"
    _write_note(vault_root / "SCHEMA.md", "# Wiki Schema\n\nsample schema\n")
    _write_note(vault_root / "index.md", "# Wiki Index\n\nsample index\n")
    _write_note(vault_root / "log.md", "# Wiki Log\n\nsample log\n")
    _write_note(
        vault_root / "entities" / "sample-api.md",
        "---\n"
        "title: sample-api\n"
        "type: entity\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample-api\n\nsample project repository service\n",
    )
    _write_note(
        vault_root / "concepts" / "sample-domain.md",
        "---\n"
        "title: sample domain\n"
        "type: concept\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample domain\n\nsample project repository service\n",
    )

    # When: caller가 entities prefix로 context graph 범위를 좁힌다.
    result = _context_service(vault_root).context(
        ContextCommand(query="sample", mode="prompt", limit=8, path_prefix="entities")
    )

    # Then: orientation은 유지되고 link target은 prefix 안 note만 반환된다.
    assert [reference.path for reference in result.orientation] == [
        "SCHEMA.md",
        "index.md",
        "log.md",
    ]
    assert [target.path for target in result.link_targets] == ["entities/sample-api.md"]
