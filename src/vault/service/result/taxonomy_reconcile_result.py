from common.model import FrozenModel


class TaxonomyReconcileResult(FrozenModel):
    dry_run: bool
    unknown_tags: list[str]
    tag_usage_counts: dict[str, int]
    planned_changes: list[str]
    changed_files: list[str]
