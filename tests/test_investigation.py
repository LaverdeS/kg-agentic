from datetime import UTC, datetime

import pytest

from kg_agentic.investigation import InvestigationAgent
from kg_agentic.models import (
    DraftBrief,
    DraftClaim,
    EvidenceItem,
    EvidenceKind,
    InvestigationRequest,
    Relationship,
    StructuralPath,
)


class RecordedStructuralSource:
    async def find_paths(self, *, project_iris: tuple[str, ...]) -> tuple[StructuralPath, ...]:
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
    async def search(self, *, query: str, corpus_id: str, limit: int) -> tuple[EvidenceItem, ...]:
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
        return DraftBrief(
            decision="Prioritise a feasibility study, not a procurement decision.",
            recommendation="Keep HERCCULES as an emerging validation path.",
            alternatives=("Use mature CEMCAP evidence as the comparison baseline.",),
            uncertainty="HERCCULES had not reported experimental results in the cited record.",
            next_action="Request current pilot results and site-specific utility data.",
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
            decision="Do not decide from unsupported output.",
            recommendation="A claim with no retrieved source should be removed.",
            alternatives=(),
            uncertainty="The model cited an unknown evidence identifier.",
            next_action="Retrieve an authoritative source.",
            claims=(DraftClaim(text="Unsupported material claim.", evidence_ids=("missing",)),),
        )


class MustNotBeCalled:
    async def find_paths(self, **kwargs):
        raise AssertionError("historical requests must stop before retrieval")

    async def search(self, **kwargs):
        raise AssertionError("historical requests must stop before retrieval")

    async def generate(self, **kwargs):
        raise AssertionError("historical requests must stop before generation")


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
    assert result.gaps == ("Unsupported material claim omitted: Unsupported material claim.",)


@pytest.mark.asyncio
async def test_historical_request_stops_before_current_evidence_is_queried() -> None:
    never = MustNotBeCalled()
    agent = InvestigationAgent(
        structural_source=never,
        evidence_memory=never,
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

    assert result.status == "unsupported_historical_request"
    assert result.evidence == ()
    assert result.brief is None
