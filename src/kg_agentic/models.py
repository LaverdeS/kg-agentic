from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal


class EvidenceKind(StrEnum):
    STRUCTURED_FACT = "structured_fact"
    SOURCE_CLAIM = "source_claim"
    MODEL_EXTRACTION = "model_extraction"
    HYPOTHESIS = "hypothesis"


@dataclass(frozen=True, slots=True)
class InvestigationRequest:
    question: str
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class Relationship:
    subject: str
    predicate: str
    object: str
    source_url: str
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class StructuralPath:
    relationships: tuple[Relationship, ...]


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    id: str
    corpus_id: str
    kind: EvidenceKind
    text: str
    source_url: str
    source_category: str
    content_hash: str
    retrieved_at: datetime
    published_at: datetime | None
    event_at: datetime | None
    passage: str | None = None
    canonical_entity_iris: tuple[str, ...] = ()
    updated_at: datetime | None = None
    ingested_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SourceDocument:
    dataset_id: str
    corpus_id: str
    source_id: str
    source_url: str
    source_category: str
    text: str
    passage: str
    kind: EvidenceKind
    canonical_entity_iris: tuple[str, ...]
    publication_at: datetime | None
    update_at: datetime | None
    event_at: datetime | None
    retrieved_at: datetime
    raw_payload: bytes | None = None


@dataclass(frozen=True, slots=True)
class DraftClaim:
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DraftBrief:
    decision: str
    recommendation: str
    alternatives: tuple[str, ...]
    uncertainty: str
    next_action: str
    claims: tuple[DraftClaim, ...]


@dataclass(frozen=True, slots=True)
class Citation:
    evidence_id: str
    source_url: str
    source_category: str
    passage: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class SupportedClaim:
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class RecommendationBrief:
    decision: str
    recommendation: str
    alternatives: tuple[str, ...]
    uncertainty: str
    next_action: str
    claims: tuple[SupportedClaim, ...]


@dataclass(frozen=True, slots=True)
class InvestigationPlan:
    question: str
    actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TraceStep:
    action: str
    count: int | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class InvestigationResult:
    status: Literal["completed", "abstained", "unsupported_historical_request"]
    plan: InvestigationPlan
    trace: tuple[TraceStep, ...]
    paths: tuple[StructuralPath, ...]
    evidence: tuple[EvidenceItem, ...]
    brief: RecommendationBrief | None
    gaps: tuple[str, ...]
