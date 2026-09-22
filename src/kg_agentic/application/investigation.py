from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from urllib.parse import urlparse

from kg_agentic.knowledge.models import (
    Citation,
    DraftBrief,
    DraftClaim,
    EvidenceItem,
    InvestigationComparison,
    InvestigationPlan,
    InvestigationRequest,
    InvestigationResult,
    RecommendationBrief,
    StructuralPath,
    SupportedClaim,
    TraceStep,
)
from kg_agentic.knowledge.temporal import is_evidence_public_by, is_path_public_by


class StructuralSource(Protocol):
    async def find_paths(
        self, *, project_iris: tuple[str, ...], as_of: datetime | None = None
    ) -> tuple[StructuralPath, ...]: ...


class EvidenceMemory(Protocol):
    async def search(
        self, *, query: str, corpus_id: str, limit: int, as_of: datetime | None = None
    ) -> tuple[EvidenceItem, ...]: ...


class BriefGenerator(Protocol):
    async def generate(
        self,
        *,
        question: str,
        plan: InvestigationPlan,
        paths: tuple[StructuralPath, ...],
        evidence: tuple[EvidenceItem, ...],
    ) -> DraftBrief: ...


class InvestigationAgent:
    """Run a bounded investigation and admit only claims with resolvable evidence."""

    def __init__(
        self,
        *,
        structural_source: StructuralSource,
        evidence_memory: EvidenceMemory,
        brief_generator: BriefGenerator,
        project_iris: Sequence[str],
        corpus_id: str,
        evidence_limit: int = 8,
    ) -> None:
        if not project_iris:
            raise ValueError("At least one project IRI is required")
        if evidence_limit < 1:
            raise ValueError("evidence_limit must be positive")
        self._structural_source = structural_source
        self._evidence_memory = evidence_memory
        self._brief_generator = brief_generator
        self._project_iris = tuple(project_iris)
        self._corpus_id = corpus_id
        self._evidence_limit = evidence_limit

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        question = request.question.strip()
        if not question:
            raise ValueError("question must not be empty")

        plan = InvestigationPlan(
            question=question,
            actions=(
                "Inspect organization-project-output paths for the configured seed corpus.",
                "Retrieve corpus-scoped semantic evidence relevant to the decision.",
                "Generate a bounded recommendation and reject claims without support.",
            ),
        )
        trace = [TraceStep(action="plan", count=len(plan.actions))]

        paths = await self._structural_source.find_paths(
            project_iris=self._project_iris, as_of=request.as_of
        )
        if request.as_of is not None:
            paths = tuple(path for path in paths if is_path_public_by(path, request.as_of))
        trace.append(TraceStep(action="retrieve_structural_paths", count=len(paths)))

        evidence = await self._evidence_memory.search(
            query=question,
            corpus_id=self._corpus_id,
            limit=self._evidence_limit,
            as_of=request.as_of,
        )
        if request.as_of is not None:
            evidence = tuple(
                item for item in evidence if is_evidence_public_by(item, request.as_of)
            )
        trace.append(TraceStep(action="retrieve_semantic_evidence", count=len(evidence)))

        if not evidence:
            missing = []
            if not paths:
                missing.append(
                    "No organization-project-output path was retrieved with dated public "
                    "availability."
                    if request.as_of is not None
                    else "No organization-project-output path was retrieved."
                )
            if not evidence:
                missing.append("No semantic evidence was retrieved from the configured corpus.")
            trace.append(TraceStep(action="check_support", detail="abstained"))
            return InvestigationResult(
                status="abstained",
                plan=plan,
                trace=tuple(trace),
                paths=paths,
                evidence=evidence,
                brief=None,
                gaps=tuple(missing),
            )

        draft = await self._brief_generator.generate(
            question=question,
            plan=plan,
            paths=paths,
            evidence=evidence,
        )
        brief, gaps = _resolve_supported_claims(draft, evidence, as_of=request.as_of)
        evidence_ids = {item.id for item in evidence}
        conflicts = tuple(
            item.id
            for item in evidence
            if any(conflict_id in evidence_ids for conflict_id in item.contradicts_ids)
        )
        if conflicts:
            gaps = (
                *gaps,
                "Conflicting source versions were retrieved and remain unresolved: "
                + ", ".join(conflicts),
            )
        if request.as_of is not None and not paths:
            gaps = (
                "No organization-project-output path had dated public availability by the cutoff; "
                "the historical brief is supported by source evidence only.",
                *gaps,
            )
        trace.append(
            TraceStep(
                action="check_support",
                count=len(brief.claims) if brief else 0,
                detail="completed" if brief else "abstained",
            )
        )
        return InvestigationResult(
            status="completed" if brief else "abstained",
            plan=plan,
            trace=tuple(trace),
            paths=paths,
            evidence=evidence,
            brief=brief,
            gaps=gaps,
        )


def _resolve_supported_claims(
    draft: DraftBrief,
    evidence: tuple[EvidenceItem, ...],
    *,
    as_of: datetime | None = None,
) -> tuple[RecommendationBrief | None, tuple[str, ...]]:
    evidence_by_id = {item.id: item for item in evidence}
    gaps: list[str] = []

    def resolve(claim: DraftClaim) -> SupportedClaim | None:
        citations = tuple(
            Citation(
                evidence_id=item.id,
                source_url=item.source_url,
                source_category=item.source_category,
                passage=item.passage or item.text,
                content_hash=item.content_hash,
            )
            for evidence_id in claim.evidence_ids
            if (item := evidence_by_id.get(evidence_id)) is not None
            and _is_resolvable_url(item.source_url)
            and (as_of is None or is_evidence_public_by(item, as_of))
        )
        if not citations:
            gaps.append(f"Unsupported material statement omitted: {claim.text}")
            return None
        return SupportedClaim(text=claim.text, citations=citations)

    decision = resolve(draft.decision)
    recommendation = resolve(draft.recommendation)
    uncertainty = resolve(draft.uncertainty)
    next_action = resolve(draft.next_action)
    alternatives = tuple(filter(None, (resolve(item) for item in draft.alternatives)))
    supported_claims = tuple(filter(None, (resolve(item) for item in draft.claims)))

    if (
        decision is None
        or recommendation is None
        or uncertainty is None
        or next_action is None
    ):
        return None, tuple(gaps)

    return (
        RecommendationBrief(
            decision=decision,
            recommendation=recommendation,
            alternatives=alternatives,
            uncertainty=uncertainty,
            next_action=next_action,
            claims=supported_claims,
        ),
        tuple(gaps),
    )


def compare_investigations(
    *,
    earlier: InvestigationResult,
    earlier_as_of: datetime,
    later: InvestigationResult,
    later_as_of: datetime,
    earlier_eligible_evidence: tuple[EvidenceItem, ...],
    later_eligible_evidence: tuple[EvidenceItem, ...],
) -> InvestigationComparison:
    """Compare full cutoff-eligible source versions independently of retrieval rank."""
    if later_as_of <= earlier_as_of:
        raise ValueError("later_as_of must be after earlier_as_of")

    earlier_by_id = {item.id: item for item in earlier.evidence}
    later_by_id = {item.id: item for item in later.evidence}
    earlier_eligible_by_id = {item.id: item for item in earlier_eligible_evidence}
    later_eligible_by_id = {item.id: item for item in later_eligible_evidence}
    newly_eligible = tuple(
        item for item in later_eligible_evidence if item.id not in earlier_eligible_by_id
    )
    no_longer_eligible = tuple(
        item for item in earlier_eligible_evidence if item.id not in later_eligible_by_id
    )
    later_only = tuple(item for item in later.evidence if item.id not in earlier_by_id)
    no_longer_retrieved = tuple(item for item in earlier.evidence if item.id not in later_by_id)
    changes = tuple(
        [
            f"Newly eligible source version: "
            f"{item.id} ({item.source_url}; {item.content_hash})."
            for item in newly_eligible
        ]
        + [
            (
                f"No longer retrieved as eligible evidence: {item.id} ({item.source_url}; "
                f"{item.content_hash})."
            )
            for item in no_longer_eligible
        ]
        or ["No retrieved eligible evidence changed between the two cutoffs."]
    )
    return InvestigationComparison(
        earlier_as_of=earlier_as_of,
        earlier=earlier,
        later_as_of=later_as_of,
        later=later,
        newly_eligible_evidence=newly_eligible,
        no_longer_eligible_evidence=no_longer_eligible,
        later_only_retrieved_evidence=later_only,
        no_longer_retrieved_evidence=no_longer_retrieved,
        changes=changes,
    )


def _is_resolvable_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
