from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from kg_agentic.infrastructure.openai_brief import OpenAIBriefGenerator
from kg_agentic.knowledge.models import (
    EvidenceItem,
    EvidenceKind,
    InvestigationPlan,
    Relationship,
    StructuralPath,
)


class FakeResponses:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        schema = kwargs["text_format"]
        return SimpleNamespace(
            output_parsed=schema(
                decision={"text": "Run a feasibility study.", "evidence_ids": ["evidence-1"]},
                recommendation={"text": "Compare two pathways.", "evidence_ids": ["evidence-1"]},
                alternatives=[{"text": "Delay the shortlist.", "evidence_ids": ["evidence-1"]}],
                uncertainty={
                    "text": "Objectives are not outcomes.",
                    "evidence_ids": ["evidence-1"],
                },
                next_action={"text": "Request normalized data.", "evidence_ids": ["evidence-1"]},
                claims=[
                    {
                        "text": "CEMCAP reports retrofit comparison objectives.",
                        "evidence_ids": ["evidence-1"],
                    }
                ],
            ),
            usage=SimpleNamespace(input_tokens=100, output_tokens=50, total_tokens=150),
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.responses = FakeResponses()


@pytest.mark.asyncio
async def test_openai_brief_uses_structured_output_and_supplied_evidence_ids() -> None:
    client = FakeOpenAI()
    generator = OpenAIBriefGenerator(client, model="gpt-test", max_output_tokens=800)
    evidence = (
        EvidenceItem(
            id="evidence-1",
            corpus_id="dataset:corpus",
            kind=EvidenceKind.SOURCE_CLAIM,
            text="A source-reported project objective.",
            source_url="https://example.test/source",
            source_category="project_record",
            content_hash="sha256:abc",
            retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
            published_at=None,
            event_at=None,
        ),
    )
    paths = (
        StructuralPath(
            relationships=(Relationship("a", "relatesTo", "b", "https://example.test"),)
        ),
    )

    draft = await generator.generate(
        question="What should be shortlisted?",
        plan=InvestigationPlan("What should be shortlisted?", ("retrieve",)),
        paths=paths,
        evidence=evidence,
    )

    assert draft.claims[0].evidence_ids == ("evidence-1",)
    assert draft.recommendation.evidence_ids == ("evidence-1",)
    assert client.responses.kwargs is not None
    assert client.responses.kwargs["model"] == "gpt-test"
    assert client.responses.kwargs["max_output_tokens"] == 800
    assert client.responses.kwargs["store"] is False
    assert generator.last_usage == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
