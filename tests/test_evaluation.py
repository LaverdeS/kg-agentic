from datetime import UTC, datetime

import pytest

from kg_agentic.application.evaluation import EvaluationQuestion, evaluate_questions
from kg_agentic.knowledge.models import (
    Citation,
    EvidenceItem,
    EvidenceKind,
    InvestigationPlan,
    InvestigationResult,
    RecommendationBrief,
    Relationship,
    StructuralPath,
    SupportedClaim,
)


def _completed_result() -> InvestigationResult:
    evidence = EvidenceItem(
        id="cordis:result:641185",
        corpus_id="cordis:cement:v1",
        kind=EvidenceKind.SOURCE_CLAIM,
        text="Pilot test evidence for CEMCAP 641185.",
        source_url="https://example.test/641185",
        source_category="publication_full_text",
        content_hash="sha256:evidence",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        event_at=None,
        passage="Pilot evidence.",
    )
    citation = Citation(
        evidence_id=evidence.id,
        source_url=evidence.source_url,
        source_category=evidence.source_category,
        passage=evidence.passage or evidence.text,
        content_hash=evidence.content_hash,
    )
    statement = SupportedClaim("Commission a feasibility study.", (citation,))
    return InvestigationResult(
        status="completed",
        plan=InvestigationPlan("What should we do?", ("retrieve",)),
        trace=(),
        paths=(
            StructuralPath(
                (
                    Relationship("project:641185", "hasResult", "result:1", "https://example.test"),
                    Relationship("result:1", "supports", "decision:1", "https://example.test"),
                )
            ),
        ),
        evidence=(evidence,),
        brief=RecommendationBrief(
            decision=statement,
            recommendation=statement,
            alternatives=(statement,),
            uncertainty=statement,
            next_action=statement,
            claims=(statement,),
        ),
        gaps=(),
    )


@pytest.mark.asyncio
async def test_evaluation_reports_support_temporal_and_consulting_metrics() -> None:
    async def run(_request):
        return _completed_result(), {"total_tokens": 12}

    report = await evaluate_questions(
        questions=(
            EvaluationQuestion(
                id="test-question",
                question="What should we do?",
                reference_identifiers=("641185",),
                reference_paths=("project -> result -> decision",),
                expected_status="completed",
                requires_multihop=True,
            ),
        ),
        runners={"agent": run},
        baseline_notes={"agent": "Structural and semantic retrieval."},
    )

    run_report = report.runs[0]
    assert run_report.status == "completed"
    assert run_report.metrics["citation_correctness"] == 1.0
    assert run_report.metrics["faithfulness_proxy"] == 1.0
    assert run_report.metrics["temporal_leakage"] == 0.0
    assert run_report.metrics["multi_hop_retrieval"] == 1.0
    assert run_report.metrics["useful_completion_or_abstention"] == 1.0
    assert run_report.metrics["consulting_rubric"] == 6.0
    assert run_report.usage == {"total_tokens": 12}
    assert run_report.limitations == "Structural and semantic retrieval."


@pytest.mark.asyncio
async def test_evaluation_records_runner_failure_without_claiming_a_score() -> None:
    async def fail(_request):
        raise RuntimeError("Neo4j unavailable")

    report = await evaluate_questions(
        questions=(EvaluationQuestion(id="test-question", question="What should we do?"),),
        runners={"agent": fail},
        baseline_notes={"agent": "Structural and semantic retrieval."},
    )

    run_report = report.runs[0]
    assert run_report.status == "failed"
    assert run_report.metrics == {}
    assert run_report.failure == "RuntimeError: Neo4j unavailable"
    assert report.has_failures is True


@pytest.mark.asyncio
async def test_evaluation_runs_both_cutoffs_for_change_monitoring() -> None:
    calls = []

    async def run(request):
        calls.append(request.as_of)
        return _completed_result(), {}

    earlier = datetime(2019, 1, 1, tzinfo=UTC)
    later = datetime(2020, 1, 1, tzinfo=UTC)
    report = await evaluate_questions(
        questions=(
            EvaluationQuestion(
                id="change-question",
                question="What changed?",
                as_of=later,
                comparison_from=earlier,
                expected_status="completed",
            ),
        ),
        runners={"agent": run},
        baseline_notes={"agent": "Structural and semantic retrieval."},
    )

    run_report = report.runs[0]
    assert calls == [earlier, later]
    assert run_report.earlier_result is not None
    assert run_report.metrics["cutoff_comparison_executed"] == 1.0
