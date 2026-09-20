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


class BridgeGraph:
    async def find_paths(self, *, project_iris):
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
    async def search(self, *, query, corpus_id, limit):
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
        return DraftBrief(
            decision="Commission a bearing-replacement design.",
            recommendation="Validate the inspection finding on site.",
            alternatives=("Increase monitoring frequency.",),
            uncertainty="The fixture contains one inspection.",
            next_action="Perform an on-site bearing assessment.",
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
