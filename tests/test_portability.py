from datetime import UTC, datetime

import pytest

from kg_agentic.application.evaluation import EvaluationQuestion, evaluate_questions
from kg_agentic.application.investigation import InvestigationAgent
from kg_agentic.knowledge.models import (
    DraftBrief,
    DraftClaim,
    EvidenceItem,
    EvidenceKind,
    InvestigationRequest,
    Relationship,
    StructuralPath,
)


class BridgeGraph:
    async def find_paths(self, *, project_iris, as_of=None):
        return (
            StructuralPath(
                relationships=(
                    Relationship(
                        "asset:bridge-42", "hasInspection", "inspection:7", "https://example.test/7"
                    ),
                    Relationship(
                        "inspection:7",
                        "recommendsAction",
                        "action:bearing-replacement",
                        "https://example.test/7",
                    ),
                )
            ),
        )


class InspectionMemory:
    async def search(self, *, query, corpus_id, limit, as_of=None):
        return (
            EvidenceItem(
                id="roads:inspection:7:v1",
                corpus_id=corpus_id,
                kind=EvidenceKind.SOURCE_CLAIM,
                text="The inspection recommends bearing replacement.",
                source_url="https://example.test/7",
                source_category="inspection",
                content_hash="sha256:inspection",
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                published_at=datetime(2025, 12, 1, tzinfo=UTC),
                event_at=datetime(2025, 11, 1, tzinfo=UTC),
            ),
        )


class MaintenanceBrief:
    async def generate(self, **kwargs):
        support = ("roads:inspection:7:v1",)
        return DraftBrief(
            decision=DraftClaim("Commission a bearing-replacement design.", support),
            recommendation=DraftClaim("Validate the inspection finding on site.", support),
            alternatives=(DraftClaim("Increase monitoring frequency.", support),),
            uncertainty=DraftClaim("The fixture contains one inspection.", support),
            next_action=DraftClaim("Perform an on-site bearing assessment.", support),
            claims=(
                DraftClaim(
                    "An inspection recommends replacement.",
                    ("roads:inspection:7:v1",),
                ),
            ),
        )


@pytest.mark.asyncio
async def test_investigation_contract_is_not_coupled_to_cordis_vocabulary() -> None:
    agent = InvestigationAgent(
        structural_source=BridgeGraph(),
        evidence_memory=InspectionMemory(),
        brief_generator=MaintenanceBrief(),
        project_iris=("asset:bridge-42",),
        corpus_id="roads:bridge-inspections:v1",
    )

    result = await agent.investigate(
        InvestigationRequest("What maintenance should be commissioned?")
    )

    assert result.status == "completed"
    assert result.brief is not None
    assert result.brief.claims[0].citations[0].source_category == "inspection"


@pytest.mark.asyncio
async def test_non_cordis_fixture_applies_the_same_historical_eligibility_rule() -> None:
    agent = InvestigationAgent(
        structural_source=BridgeGraph(),
        evidence_memory=InspectionMemory(),
        brief_generator=MaintenanceBrief(),
        project_iris=("asset:bridge-42",),
        corpus_id="roads:bridge-inspections:v1",
    )

    before_publication = await agent.investigate(
        InvestigationRequest(
            "What maintenance should be commissioned?",
            as_of=datetime(2025, 6, 1, tzinfo=UTC),
        )
    )
    after_publication = await agent.investigate(
        InvestigationRequest(
            "What maintenance should be commissioned?",
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    assert before_publication.status == "abstained"
    assert after_publication.status == "completed"
    assert after_publication.brief is not None
    assert any("source evidence only" in gap for gap in after_publication.gaps)


@pytest.mark.asyncio
async def test_non_cordis_fixture_runs_through_the_shared_evaluation_seam() -> None:
    agent = InvestigationAgent(
        structural_source=BridgeGraph(),
        evidence_memory=InspectionMemory(),
        brief_generator=MaintenanceBrief(),
        project_iris=("asset:bridge-42",),
        corpus_id="roads:bridge-inspections:v1",
    )

    async def run(request):
        return await agent.investigate(request), {"total_tokens": 0}

    report = await evaluate_questions(
        questions=(
            EvaluationQuestion(
                id="bridge-maintenance",
                question="What maintenance should be commissioned?",
                as_of=datetime(2026, 1, 1, tzinfo=UTC),
                reference_identifiers=("bridge-42",),
                expected_status="completed",
            ),
        ),
        runners={"fixture_agent": run},
        baseline_notes={"fixture_agent": "Synthetic roads-inspection fixture."},
    )

    assert report.has_failures is False
    assert report.runs[0].status == "completed"
    assert report.runs[0].metrics["citation_correctness"] == 1.0
