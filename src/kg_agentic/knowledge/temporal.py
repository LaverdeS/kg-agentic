from datetime import UTC, datetime

from kg_agentic.knowledge.models import EvidenceItem, StructuralPath


def is_evidence_public_by(item: EvidenceItem, as_of: datetime) -> bool:
    """Return whether source availability, rather than event or ingestion time, is proven."""
    cutoff = _utc(as_of)
    if item.updated_at is not None:
        return _utc(item.updated_at) <= cutoff
    if item.published_at is not None:
        return _utc(item.published_at) <= cutoff
    if item.publication_year is not None and item.publication_precision == "year":
        return cutoff.year > item.publication_year
    return False


def is_path_public_by(path: StructuralPath, as_of: datetime) -> bool:
    """A structural path is historical only when every relationship has dated availability."""
    cutoff = _utc(as_of)
    return bool(path.relationships) and all(
        relationship.available_at is not None and _utc(relationship.available_at) <= cutoff
        for relationship in path.relationships
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
