from datetime import UTC, datetime

import pytest

from kg_agentic.application.investigation import InvestigationAgent, compare_investigations
from kg_agentic.knowledge.models import (
    DraftBrief,
    DraftClaim,
    EvidenceItem,
    EvidenceKind,
    InvestigationRequest,
    Relationship,
    StructuralPath,
)


class RecordedStructuralSource:
    async def find_paths(
        self, *, project_iris: tuple[str, ...], as_of=None
    ) -> tuple[StructuralPath, ...]:
        return (
            StructuralPath(
                relationships=(
                    Relationship(
                        subject="eurio:organisation/leap",
                        predicate="eurio:coordinator",
                        object="eurio:project/herccules",
                        source_url="https://cordis.europa.eu/project/id/101096691",
                    ),
                    Relationship(
                        subject="eurio:project/herccules",
                        predicate="eurio:hasResult",
                        object="eurio:result/d4-1",
                        source_url="https://cordis.europa.eu/project/id/101096691/results",
                    ),
                )
            ),
        )


class RecordedEvidenceMemory:
    async def search(
        self, *, query: str, corpus_id: str, limit: int, as_of=None
    ) -> tuple[EvidenceItem, ...]:
        return (
            EvidenceItem(
                id="cordis:101096691:record:v1",
                corpus_id=corpus_id,
                kind=EvidenceKind.SOURCE_CLAIM,
                text=(
                    "The first reporting-period summary says experimental results were not yet "
                    "available and describes planned pilot validation."
                ),
                source_url="https://cordis.europa.eu/project/id/101096691/reporting",
                source_category="project_record",
                content_hash="sha256:recorded-herccules",
                retrieved_at=datetime(2026, 9, 19, tzinfo=UTC),
                published_at=None,
                event_at=None,
            ),
        )


class ControlledBriefGenerator:
    async def generate(self, *, question, plan, paths, evidence):
        support = ("cordis:101096691:record:v1",)
        return DraftBrief(
            decision=DraftClaim("Prioritise a feasibility study.", support),
            recommendation=DraftClaim("Keep HERCCULES as a validation path.", support),
            alternatives=(DraftClaim("Use a comparison baseline.", support),),
            uncertainty=DraftClaim("The cited record reports no experimental results.", support),
            next_action=DraftClaim("Request current pilot results.", support),
            claims=(
                DraftClaim(
                    text="HERCCULES had no experimental results in the cited reporting period.",
                    evidence_ids=("cordis:101096691:record:v1",),
                ),
            ),
        )


class UnsupportedBriefGenerator:
    async def generate(self, *, question, plan, paths, evidence):
        return DraftBrief(
            decision=DraftClaim("Do not decide from unsupported output.", ("missing",)),
            recommendation=DraftClaim(
                "A claim with no retrieved source should be removed.", ("missing",)
            ),
            alternatives=(),
            uncertainty=DraftClaim("The model cited an unknown evidence identifier.", ("missing",)),
            next_action=DraftClaim("Retrieve an authoritative source.", ("missing",)),
            claims=(DraftClaim(text="Unsupported material claim.", evidence_ids=("missing",)),),
        )


class MustNotBeCalled:
    async def generate(self, **kwargs):
        raise AssertionError("historical requests without eligible evidence must not generate")


class EmptyHistoricalEvidenceMemory:
    async def search(self, **kwargs):
        return ()


class HistoricalStructuralSource:
    async def find_paths(self, *, project_iris, as_of=None):
        return (
            StructuralPath(
                relationships=(
                    Relationship(
                        subject="eurio:project/historical",
                        predicate="eurio:hasResult",
                        object="eurio:result/dated",
                        source_url="https://example.test/dated",
                        available_at=datetime(2024, 5, 1, tzinfo=UTC),
                    ),
                )
            ),
            StructuralPath(
                relationships=(
                    Relationship(
                        subject="eurio:project/future",
                        predicate="eurio:hasResult",
                        object="eurio:result/future",
                        source_url="https://example.test/future",
                        available_at=datetime(2026, 1, 1, tzinfo=UTC),
                    ),
                )
            ),
        )


class HistoricalEvidenceMemory:
    async def search(self, *, query, corpus_id, limit, as_of=None):
        return (
            EvidenceItem(
                id="dated",
                corpus_id=corpus_id,
                kind=EvidenceKind.SOURCE_CLAIM,
                text="A dated source supports a historical claim.",
                source_url="https://example.test/dated",
                source_category="publication",
                content_hash="sha256:dated",
                retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
                published_at=datetime(2024, 5, 1, tzinfo=UTC),
                event_at=datetime(2024, 4, 1, tzinfo=UTC),
            ),
            EvidenceItem(
                id="future",
                corpus_id=corpus_id,
                kind=EvidenceKind.SOURCE_CLAIM,
                text="A future source must not affect the earlier brief.",
                source_url="https://example.test/future",
                source_category="publication",
                content_hash="sha256:future",
                retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
                event_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
            EvidenceItem(
                id="unknown-publication-date",
                corpus_id=corpus_id,
                kind=EvidenceKind.SOURCE_CLAIM,
                text="An event date does not prove this source was public then.",
                source_url="https://example.test/unknown",
                source_category="project_record",
                content_hash="sha256:unknown",
                retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
                published_at=None,
                event_at=datetime(2020, 1, 1, tzinfo=UTC),
            ),
        )


class HistoricalBriefGenerator:
    def __init__(self) -> None:
        self.evidence_ids: tuple[str, ...] = ()

    async def generate(self, *, question, plan, paths, evidence):
        self.evidence_ids = tuple(item.id for item in evidence)
        support = ("dated",)
        return DraftBrief(
            decision=DraftClaim("Use the historically public evidence.", support),
            recommendation=DraftClaim("Commission a validation step.", support),
            alternatives=(),
            uncertainty=DraftClaim("Only one dated source is available.", support),
            next_action=DraftClaim("Seek an independently dated source.", support),
            claims=(DraftClaim("The dated source supports this claim.", support),),
        )


@pytest.mark.asyncio
async def test_current_investigation_returns_supported_cited_brief() -> None:
    agent = InvestigationAgent(
        structural_source=RecordedStructuralSource(),
        evidence_memory=RecordedEvidenceMemory(),
        brief_generator=ControlledBriefGenerator(),
        project_iris=("eurio:project/herccules",),
        corpus_id="cordis:cement:v1",
    )

    result = await agent.investigate(
        InvestigationRequest(
            question="Which capture pathways merit a cement retrofit feasibility study?"
        )
    )

    assert result.status == "completed"
    assert len(result.paths[0].relationships) == 2
    assert result.brief is not None
    assert result.brief.claims[0].citations[0].source_url.endswith("/reporting")
    assert result.brief.claims[0].citations[0].evidence_id == "cordis:101096691:record:v1"
    assert [step.action for step in result.trace] == [
        "plan",
        "retrieve_structural_paths",
        "retrieve_semantic_evidence",
        "check_support",
    ]


@pytest.mark.asyncio
async def test_unsupported_generated_claim_is_removed_and_agent_abstains() -> None:
    agent = InvestigationAgent(
        structural_source=RecordedStructuralSource(),
        evidence_memory=RecordedEvidenceMemory(),
        brief_generator=UnsupportedBriefGenerator(),
        project_iris=("eurio:project/herccules",),
        corpus_id="cordis:cement:v1",
    )

    result = await agent.investigate(InvestigationRequest(question="What is supported?"))

    assert result.status == "abstained"
    assert result.brief is None
    assert "Unsupported material statement omitted" in result.gaps[0]


@pytest.mark.asyncio
async def test_historical_request_abstains_when_no_evidence_has_public_availability() -> None:
    never = MustNotBeCalled()
    agent = InvestigationAgent(
        structural_source=HistoricalStructuralSource(),
        evidence_memory=EmptyHistoricalEvidenceMemory(),
        brief_generator=never,
        project_iris=("eurio:project/herccules",),
        corpus_id="cordis:cement:v1",
    )

    result = await agent.investigate(
        InvestigationRequest(
            question="What was supported then?",
            as_of=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )

    assert result.status == "abstained"
    assert result.evidence == ()
    assert result.brief is None


@pytest.mark.asyncio
async def test_historical_investigation_excludes_future_and_undated_evidence_before_generation(
) -> None:
    generator = HistoricalBriefGenerator()
    agent = InvestigationAgent(
        structural_source=HistoricalStructuralSource(),
        evidence_memory=HistoricalEvidenceMemory(),
        brief_generator=generator,
        project_iris=("eurio:project/historical",),
        corpus_id="cordis:cement:v1",
    )

    result = await agent.investigate(
        InvestigationRequest(
            question="What was supported then?",
            as_of=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )

    assert result.status == "completed"
    assert tuple(item.id for item in result.evidence) == ("dated",)
    assert generator.evidence_ids == ("dated",)
    assert len(result.paths) == 1
    assert result.paths[0].relationships[0].object == "eurio:result/dated"


@pytest.mark.asyncio
async def test_comparison_attributes_newly_eligible_evidence_to_its_source_version() -> None:
    agent = InvestigationAgent(
        structural_source=HistoricalStructuralSource(),
        evidence_memory=HistoricalEvidenceMemory(),
        brief_generator=HistoricalBriefGenerator(),
        project_iris=("eurio:project/historical",),
        corpus_id="cordis:cement:v1",
    )
    question = "What changed in the available support?"
    earlier = await agent.investigate(
        InvestigationRequest(question=question, as_of=datetime(2025, 1, 1, tzinfo=UTC))
    )
    later = await agent.investigate(
        InvestigationRequest(question=question, as_of=datetime(2027, 1, 1, tzinfo=UTC))
    )

    comparison = compare_investigations(
        earlier=earlier,
        earlier_as_of=datetime(2025, 1, 1, tzinfo=UTC),
        later=later,
        later_as_of=datetime(2027, 1, 1, tzinfo=UTC),
        earlier_eligible_evidence=earlier.evidence,
        later_eligible_evidence=later.evidence,
    )

    assert tuple(item.id for item in comparison.later_only_retrieved_evidence) == ("future",)
    assert comparison.later_only_retrieved_evidence[0].source_url == "https://example.test/future"
    assert "future" in comparison.changes[0]


def test_revised_evidence_is_not_public_before_its_update_date() -> None:
    from kg_agentic.knowledge.temporal import is_evidence_public_by

    revised = EvidenceItem(
        id="revised", corpus_id="fixture", kind=EvidenceKind.SOURCE_CLAIM, text="Corrected.",
        source_url="https://example.test/revised", source_category="inspection",
        content_hash="sha256:revised", retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC), event_at=None,
        updated_at=datetime(2025, 2, 1, tzinfo=UTC),
    )

    assert not is_evidence_public_by(revised, datetime(2025, 1, 15, tzinfo=UTC))
    assert is_evidence_public_by(revised, datetime(2025, 2, 1, tzinfo=UTC))
