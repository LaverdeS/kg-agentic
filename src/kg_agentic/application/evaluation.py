"""Run inspectable quality evaluations through an investigation-use-case seam."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Literal

from kg_agentic.knowledge.models import (
    EvidenceItem,
    InvestigationRequest,
    InvestigationResult,
    SupportedClaim,
)
from kg_agentic.knowledge.temporal import is_evidence_public_by, is_path_public_by

EvaluationRunner = Callable[
    [InvestigationRequest], Awaitable[tuple[InvestigationResult, dict[str, int]]]
]


@dataclass(frozen=True, slots=True)
class EvaluationQuestion:
    """Task configuration; source and consulting vocabulary remain data, not evaluator logic."""

    id: str
    question: str
    as_of: datetime | None = None
    comparison_from: datetime | None = None
    reference_identifiers: tuple[str, ...] = ()
    reference_paths: tuple[str, ...] = ()
    acceptable_support: tuple[str, ...] = ()
    abstain_when: tuple[str, ...] = ()
    invalid_citation_case: str | None = None
    expected_status: Literal["completed", "abstained"] | None = None
    requires_multihop: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    system: str
    question_id: str
    status: Literal["completed", "abstained", "failed"]
    result: InvestigationResult | None
    earlier_result: InvestigationResult | None
    later_only_retrieved_evidence: tuple[str, ...]
    metrics: dict[str, float]
    latency_ms: int
    usage: dict[str, int]
    limitations: str
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    system: str
    completed: int
    abstained: int
    failed: int
    mean_latency_ms: float
    total_usage: dict[str, int]
    mean_metrics: dict[str, float]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Raw runs and score summaries, deliberately separate from software-correctness tests."""

    runs: tuple[EvaluationRun, ...]
    summaries: tuple[EvaluationSummary, ...]

    @property
    def has_failures(self) -> bool:
        return any(run.status == "failed" for run in self.runs)


async def evaluate_questions(
    *,
    questions: Sequence[EvaluationQuestion],
    runners: Mapping[str, EvaluationRunner],
    baseline_notes: Mapping[str, str],
) -> EvaluationReport:
    """Run every system on the same tasks and record observable, support-focused measures."""
    if not questions:
        raise ValueError("At least one evaluation question is required")
    if not runners:
        raise ValueError("At least one evaluation runner is required")
    missing_notes = set(runners).difference(baseline_notes)
    if missing_notes:
        raise ValueError(f"Missing baseline notes for: {', '.join(sorted(missing_notes))}")
    invalid_comparisons = [
        question.id
        for question in questions
        if question.comparison_from is not None
        and (question.as_of is None or question.comparison_from >= question.as_of)
    ]
    if invalid_comparisons:
        raise ValueError(
            "comparison_from must be before as_of for: " + ", ".join(invalid_comparisons)
        )

    runs: list[EvaluationRun] = []
    for system, runner in runners.items():
        for question in questions:
            started = monotonic()
            try:
                earlier_result = None
                earlier_usage: dict[str, int] = {}
                if question.comparison_from is not None:
                    earlier_result, earlier_usage = await runner(
                        InvestigationRequest(
                            question=question.question,
                            as_of=question.comparison_from,
                        )
                    )
                result, usage = await runner(
                    InvestigationRequest(question=question.question, as_of=question.as_of)
                )
            except Exception as error:
                runs.append(
                    EvaluationRun(
                        system=system,
                        question_id=question.id,
                        status="failed",
                        result=None,
                        earlier_result=None,
                        later_only_retrieved_evidence=(),
                        metrics={},
                        latency_ms=round((monotonic() - started) * 1000),
                        usage={},
                        limitations=baseline_notes[system],
                        failure=f"{type(error).__name__}: {error}",
                    )
                )
                continue
            runs.append(
                EvaluationRun(
                    system=system,
                    question_id=question.id,
                    status=result.status,
                    result=result,
                    earlier_result=earlier_result,
                    later_only_retrieved_evidence=_later_only_evidence(earlier_result, result),
                    metrics=_metrics(question, result, earlier_result),
                    latency_ms=round((monotonic() - started) * 1000),
                    usage=_sum_usage(earlier_usage, usage),
                    limitations=baseline_notes[system],
                )
            )
    return EvaluationReport(runs=tuple(runs), summaries=_summaries(runs))


def _metrics(
    question: EvaluationQuestion,
    result: InvestigationResult,
    earlier_result: InvestigationResult | None,
) -> dict[str, float]:
    citations = tuple(
        citation for statement in _statements(result) for citation in statement.citations
    )
    evidence_by_id = {item.id: item for item in result.evidence}
    resolvable = [
        citation
        for citation in citations
        if (item := evidence_by_id.get(citation.evidence_id)) is not None
        and citation.source_url == item.source_url
        and citation.source_category == item.source_category
        and citation.content_hash == item.content_hash
        and citation.passage == (item.passage or item.text)
    ]
    citation_score = len(resolvable) / len(citations) if citations else 0.0
    all_statements_supported = bool(citations) and len(resolvable) == len(citations)
    temporal_leakage = float(_has_temporal_leakage(result, question.as_of))
    if earlier_result is not None:
        temporal_leakage = float(
            temporal_leakage or _has_temporal_leakage(earlier_result, question.comparison_from)
        )
    identifier_coverage = _identifier_coverage(question.reference_identifiers, result)
    has_multihop_path = any(len(path.relationships) >= 2 for path in result.paths)
    useful_outcome = (
        result.status == question.expected_status
        if question.expected_status is not None
        else result.status in {"completed", "abstained"}
    )
    return {
        "citation_correctness": citation_score,
        # This is an automated support-resolvability proxy, not an independent factual verdict.
        "faithfulness_proxy": float(all_statements_supported),
        "temporal_leakage": temporal_leakage,
        "reference_identifier_coverage": identifier_coverage,
        "acceptable_support_coverage": _support_coverage(
            question.acceptable_support,
            tuple(evidence_by_id[citation.evidence_id] for citation in resolvable),
        ),
        "multi_hop_retrieval": float(not question.requires_multihop or has_multihop_path),
        "useful_completion_or_abstention": float(useful_outcome),
        "cutoff_comparison_executed": float(
            question.comparison_from is None or earlier_result is not None
        ),
        "consulting_rubric": float(_consulting_rubric(result, has_multihop_path)),
    }


def _has_temporal_leakage(result: InvestigationResult, as_of: datetime | None) -> bool:
    return as_of is not None and (
        any(not is_evidence_public_by(item, as_of) for item in result.evidence)
        or any(not is_path_public_by(path, as_of) for path in result.paths)
    )


def _later_only_evidence(
    earlier_result: InvestigationResult | None, result: InvestigationResult
) -> tuple[str, ...]:
    if earlier_result is None:
        return ()
    earlier_ids = {item.id for item in earlier_result.evidence}
    return tuple(item.id for item in result.evidence if item.id not in earlier_ids)


def _support_coverage(support: Sequence[str], evidence: Sequence[EvidenceItem]) -> float:
    """Report whether configured expected support is retrieved; never infer unsupported truth."""
    if not support:
        return 1.0
    text = " ".join(
        f"{item.text} {item.passage or ''}" for item in evidence
    ).casefold()
    return sum(_support_terms(item, text) for item in support) / len(support)


def _support_terms(support: str, text: str) -> bool:
    words = [word for word in support.casefold().replace("-", " ").split() if len(word) > 3]
    return bool(words) and all(word in text for word in words)


def _statements(result: InvestigationResult) -> tuple[SupportedClaim, ...]:
    if result.brief is None:
        return ()
    brief = result.brief
    return (
        brief.decision,
        brief.recommendation,
        *brief.alternatives,
        brief.uncertainty,
        brief.next_action,
        *brief.claims,
    )


def _identifier_coverage(identifiers: Sequence[str], result: InvestigationResult) -> float:
    if not identifiers:
        return 1.0
    values = " ".join(
        [
            *(
                " ".join(
                    (
                        item.id,
                        item.source_url,
                        item.text,
                        item.passage or "",
                        *item.canonical_entity_iris,
                    )
                )
                for item in result.evidence
            ),
            *(
                " ".join(
                    value
                    for relationship in path.relationships
                    for value in (relationship.subject, relationship.predicate, relationship.object)
                )
                for path in result.paths
            ),
        ]
    ).casefold()
    return sum(identifier.casefold() in values for identifier in identifiers) / len(identifiers)


def _consulting_rubric(result: InvestigationResult, has_multihop_path: bool) -> int:
    """Transparent automated proxy; human usefulness review is reported separately as pending."""
    if result.brief is None:
        return 0
    brief = result.brief
    return sum(
        (
            bool(brief.decision.text and brief.recommendation.text),
            bool(brief.claims),
            bool(brief.alternatives),
            has_multihop_path,
            bool(brief.uncertainty.text),
            bool(brief.next_action.text),
        )
    )


def _summaries(runs: Sequence[EvaluationRun]) -> tuple[EvaluationSummary, ...]:
    summaries: list[EvaluationSummary] = []
    for system in dict.fromkeys(run.system for run in runs):
        system_runs = [run for run in runs if run.system == system]
        scored_runs = [run for run in system_runs if run.metrics]
        metric_names = {name for run in scored_runs for name in run.metrics}
        summaries.append(
            EvaluationSummary(
                system=system,
                completed=sum(run.status == "completed" for run in system_runs),
                abstained=sum(run.status == "abstained" for run in system_runs),
                failed=sum(run.status == "failed" for run in system_runs),
                mean_latency_ms=sum(run.latency_ms for run in system_runs) / len(system_runs),
                total_usage={
                    key: sum(run.usage.get(key, 0) for run in system_runs)
                    for key in sorted({key for run in system_runs for key in run.usage})
                },
                mean_metrics={
                    name: sum(run.metrics[name] for run in scored_runs) / len(scored_runs)
                    for name in sorted(metric_names)
                }
                if scored_runs
                else {},
            )
        )
    return tuple(summaries)


def _sum_usage(*usages: dict[str, int]) -> dict[str, int]:
    return {
        key: sum(usage.get(key, 0) for usage in usages)
        for key in {key for usage in usages for key in usage}
    }
