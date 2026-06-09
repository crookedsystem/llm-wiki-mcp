from common.model import FrozenModel


class VaultStatus(FrozenModel):
    note_count: int
    total_bytes: int
    note_paths: list[str]


class GraphHealth(FrozenModel):
    link_count: int
    broken_link_count: int
    orphan_count: int


class MetricsSnapshot(FrozenModel):
    vault_notes_total: int
    vault_bytes_total: int
    graph_links_total: int
    graph_broken_links_total: int
    graph_orphans_total: int


class VaultInspectionResult(FrozenModel):
    status: VaultStatus
    graph: GraphHealth
    metrics: MetricsSnapshot
