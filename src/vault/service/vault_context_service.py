from common.model import FrozenModel
from vault.service.command.context_command import ContextCommand
from vault.service.result.context_result import ContextResult
from vault.service.vault_context_section_builder import VaultContextSectionBuilder
from vault.service.vault_context_spec import ENTITY_GUIDANCE, USAGE_BY_MODE
from vault.service.vault_search_service import VaultSearchService


class VaultContextService(FrozenModel):
    search_service: VaultSearchService

    def context(self, command: ContextCommand) -> ContextResult:
        sections = VaultContextSectionBuilder(search_service=self.search_service).build_sections(
            command
        )

        return ContextResult(
            query=command.query,
            mode=command.mode,
            count=sum(len(section.notes) for section in sections),
            usage=list(USAGE_BY_MODE[command.mode]),
            entity_guidance=ENTITY_GUIDANCE,
            sections=sections,
        )
