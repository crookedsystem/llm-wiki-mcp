import asyncio
from datetime import UTC, datetime
from pathlib import Path

from vault.component.write_queue import VaultWriteQueue
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.organize_folders_command import OrganizeFoldersCommand
from vault.service.vault_folder_organization_service import VaultFolderOrganizationService

_NOW = datetime(2026, 7, 4, 12, 30, tzinfo=UTC)


def _note(title: str, note_type: str, tags: list[str], body: str = "Body") -> str:
    rendered_tags = "\n".join(f"  - {tag}" for tag in tags)
    return (
        "---\n"
        f"title: {title}\n"
        'created: "2026-07-01T00:00:00Z"\n'
        'updated: "2026-07-01T00:00:00Z"\n'
        f"type: {note_type}\n"
        "tags:\n"
        f"{rendered_tags}\n"
        "sources: []\n"
        "---\n\n"
        f"# {title}\n\n{body}\n"
    )


def _operational_note(title: str, note_type: str, body: str) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        'created: "2026-07-01T00:00:00Z"\n'
        'updated: "2026-07-01T00:00:00Z"\n'
        f"type: {note_type}\n"
        "tags:\n"
        "  - llm-wiki\n"
        "sources: []\n"
        "---\n"
        f"{body}"
    )


def _write_direct_notes(vault: Path) -> None:
    (vault / "entities").mkdir(parents=True)
    (vault / "concepts").mkdir()
    for index in range(10):
        (vault / "entities" / f"product-{index}.md").write_text(
            _note(f"Product {index}", "entity", ["product"]),
            encoding="utf-8",
        )
        (vault / "entities" / f"project-{index}.md").write_text(
            _note(f"Project {index}", "entity", ["github", "repository"]),
            encoding="utf-8",
        )
    (vault / "concepts" / "links.md").write_text(
        _note(
            "Links",
            "concept",
            ["llm-wiki"],
            "See [[entities/product-0|Product 0]] and [[project-0]].",
        ),
        encoding="utf-8",
    )
    (vault / "index.md").write_text(
        _operational_note(
            "Wiki Index",
            "index",
            "\n# Wiki Index\n\n## Entities\n"
            "- [[entities/product-0|Product 0]] — Product summary\n"
            "- [[entities/project-0|Project 0]] — Project summary\n",
        ),
        encoding="utf-8",
    )
    (vault / "log.md").write_text(
        _operational_note("Wiki Log", "log", "\n# Wiki Log\n"),
        encoding="utf-8",
    )
    (vault / "SCHEMA.md").write_text(
        _operational_note("Wiki Schema", "schema", "\n# Wiki Schema\n\n## Subfolders\n"),
        encoding="utf-8",
    )


def _service(vault: Path) -> VaultFolderOrganizationService:
    return VaultFolderOrganizationService(
        note_repository=VaultNoteRepository(root=vault),
        queue=VaultWriteQueue(),
        clock=lambda: _NOW,
    )


def test_organize_folders_dry_run은_subfolder_이동계획만_반환한다(tmp_path: Path) -> None:
    async def exercise() -> None:
        vault = tmp_path / "vault"
        _write_direct_notes(vault)
        service = _service(vault)

        result = await service.organize_folders(OrganizeFoldersCommand(root_folder="entities"))

        assert result.dry_run is True
        assert result.applied is False
        assert len(result.moves) == 20
        assert "entities/products/" in result.created_folders
        assert "entities/projects/" in result.created_folders
        assert (vault / "entities" / "product-0.md").exists()
        assert not (vault / "entities" / "products" / "product-0.md").exists()
        assert result.confirmation_phrase.startswith("ORGANIZE_FOLDERS: ")

    asyncio.run(exercise())


def test_organize_folders는_confirmation_후_파일과_링크를_함께_이동한다(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        vault = tmp_path / "vault"
        _write_direct_notes(vault)
        service = _service(vault)

        preview = await service.organize_folders(OrganizeFoldersCommand(root_folder="entities"))
        result = await service.organize_folders(
            OrganizeFoldersCommand(
                root_folder="entities",
                dry_run=False,
                confirm=preview.confirmation_phrase,
            )
        )

        assert result.applied is True
        assert (vault / "entities" / "products" / "product-0.md").exists()
        assert (vault / "entities" / "projects" / "project-0.md").exists()
        assert not (vault / "entities" / "product-0.md").exists()
        links_note = (vault / "concepts" / "links.md").read_text(encoding="utf-8")
        assert "[[entities/products/product-0|Product 0]]" in links_note
        assert "[[entities/projects/project-0]]" in links_note

        index = (vault / "index.md").read_text(encoding="utf-8")
        assert "[[entities/products/product-0|Product 0]] — Product summary" in index
        assert "[[entities/projects/project-0|Project 0]] — Project summary" in index
        assert "[[entities/product-0|Product 0]]" not in index

        schema = (vault / "SCHEMA.md").read_text(encoding="utf-8")
        assert "`entities/products/`" in schema
        assert "`entities/projects/`" in schema
        log = (vault / "log.md").read_text(encoding="utf-8")
        assert "update | entities/products/product-0" in log
        assert "Moved from entities/product-0.md" in log
        assert "SCHEMA.md" in result.updated_paths
        assert "index.md" in result.updated_paths
        assert "log.md" in result.updated_paths

    asyncio.run(exercise())


def test_organize_folders는_type과_top_folder_불일치를_바로잡는다(tmp_path: Path) -> None:
    async def exercise() -> None:
        vault = tmp_path / "vault"
        (vault / "concepts").mkdir(parents=True)
        (vault / "concepts" / "misfiled.md").write_text(
            _note("Misfiled", "entity", ["product"]),
            encoding="utf-8",
        )
        service = _service(vault)

        preview = await service.organize_folders(OrganizeFoldersCommand())

        assert [move.old_path for move in preview.moves] == ["concepts/misfiled.md"]
        assert [move.new_path for move in preview.moves] == ["entities/misfiled.md"]
        assert "type 'entity' belongs under entities/" in preview.moves[0].reason

    asyncio.run(exercise())
