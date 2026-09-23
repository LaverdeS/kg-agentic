import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from time import monotonic
from typing import Literal, cast
from uuid import uuid4

from dotenv import load_dotenv

from kg_agentic.application.cement import CORPUS_ID, CURRENT_QUESTION
from kg_agentic.application.evaluation import EvaluationQuestion
from kg_agentic.infrastructure.bootstrap import (
    compare_cement_slice,
    evaluate_cement_slice,
    frozen_cement_source_versions,
    ingest_cement_slice,
    investigate_cement_slice,
)
from kg_agentic.infrastructure.runtime import Settings
from kg_agentic.knowledge.models import (
    InvestigationComparison,
    InvestigationRequest,
    InvestigationResult,
    SupportedClaim,
)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    load_dotenv()
    run_id = str(uuid4())
    started = monotonic()
    try:
        exit_code = asyncio.run(_dispatch(args, run_id=run_id, started=started))
    except Exception as error:
        _log(
            "command_failed",
            run_id=run_id,
            command=args.command,
            source="cordis-eurio",
            corpus=CORPUS_ID,
            duration_ms=round((monotonic() - started) * 1000),
            error_type=type(error).__name__,
        )
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(exit_code)


async def _dispatch(args: argparse.Namespace, *, run_id: str, started: float) -> int:
    if args.command == "ingest":
        return await _ingest(run_id=run_id, started=started)
    if args.command == "investigate":
        return await _investigate(
            args.question,
            args.as_of,
            args.json,
            run_id=run_id,
            started=started,
        )
    if args.command == "compare":
        return await _compare(
            args.question,
            args.earlier_as_of,
            args.later_as_of,
            args.json,
            run_id=run_id,
            started=started,
        )
    if args.command == "evaluate":
        return await _evaluate(args.output, run_id=run_id, started=started)
    raise ValueError(f"Unknown command: {args.command}")


async def _ingest(*, run_id: str | None = None, started: float | None = None) -> int:
    settings = Settings.from_environment()
    run_id = run_id or str(uuid4())
    started = started if started is not None else monotonic()
    _log("ingestion_started", run_id=run_id, source="cordis-eurio", corpus=CORPUS_ID)
    report = await ingest_cement_slice(settings)
    _log(
        "ingestion_completed",
        run_id=run_id,
        source="cordis-eurio",
        corpus=CORPUS_ID,
        received=report.received,
        ingested=report.ingested,
        skipped_unchanged=report.skipped_unchanged,
        duration_ms=round((monotonic() - started) * 1000),
    )
    print(json.dumps(asdict(report), indent=2))
    return 0


async def _investigate(
    question: str,
    as_of_value: str | None,
    json_output: bool,
    *,
    run_id: str | None = None,
    started: float | None = None,
) -> int:
    as_of = _parse_as_of(as_of_value)
    settings = Settings.from_environment()
    run_id = run_id or str(uuid4())
    started = started if started is not None else monotonic()
    _log("investigation_started", run_id=run_id, source="cordis-eurio", corpus=CORPUS_ID)
    result, usage = await investigate_cement_slice(
        settings, InvestigationRequest(question=question, as_of=as_of)
    )
    _log(
        "investigation_completed",
        run_id=run_id,
        source="cordis-eurio",
        corpus=CORPUS_ID,
        status=result.status,
        paths=len(result.paths),
        evidence=len(result.evidence),
        duration_ms=round((monotonic() - started) * 1000),
        model_usage=usage,
    )
    _print_result(result, json_output=json_output)
    return 0 if result.status == "completed" else 2


async def _compare(
    question: str,
    earlier_as_of_value: str,
    later_as_of_value: str,
    json_output: bool,
    *,
    run_id: str | None = None,
    started: float | None = None,
) -> int:
    earlier_as_of = _parse_as_of(earlier_as_of_value)
    later_as_of = _parse_as_of(later_as_of_value)
    assert earlier_as_of is not None
    assert later_as_of is not None
    settings = Settings.from_environment()
    run_id = run_id or str(uuid4())
    started = started if started is not None else monotonic()
    _log("comparison_started", run_id=run_id, source="cordis-eurio", corpus=CORPUS_ID)
    comparison, usage = await compare_cement_slice(
        settings,
        question=question,
        earlier_as_of=earlier_as_of,
        later_as_of=later_as_of,
    )
    _log(
        "comparison_completed",
        run_id=run_id,
        source="cordis-eurio",
        corpus=CORPUS_ID,
        earlier_status=comparison.earlier.status,
        later_status=comparison.later.status,
        later_only_retrieved_evidence=len(comparison.later_only_retrieved_evidence),
        duration_ms=round((monotonic() - started) * 1000),
        model_usage=usage,
    )
    _print_comparison(comparison, json_output=json_output)
    return 0 if comparison.earlier.status == comparison.later.status == "completed" else 2


async def _evaluate(
    output_value: str | None,
    *,
    run_id: str | None = None,
    started: float | None = None,
) -> int:
    settings = Settings.from_environment()
    run_id = run_id or str(uuid4())
    started = started if started is not None else monotonic()
    raw_questions = _read_evaluation_questions()
    questions = tuple(_evaluation_question(item) for item in raw_questions)
    frozen_source_versions = frozen_cement_source_versions(settings)
    _log(
        "evaluation_started",
        run_id=run_id,
        source="cordis-eurio",
        corpus=CORPUS_ID,
        questions=len(questions),
        systems=("agent", "eurio_only", "semantic_only"),
    )
    report = await evaluate_cement_slice(settings, questions)
    output = (
        Path(output_value)
        if output_value is not None
        else settings.data_dir / "evaluations" / f"cement-retrofit-{run_id}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC),
        "corpus": {
            "dataset_id": "cordis-eurio",
            "corpus_id": CORPUS_ID,
            "source_versions": frozen_source_versions,
        },
        "generation_settings": {
            "model": settings.model,
            "model_max_output_tokens": settings.model_max_output_tokens,
            "evidence_limit": settings.evidence_limit,
        },
        "questions": raw_questions,
        "report": asdict(report),
        "measurement_notes": {
            "faithfulness_proxy": (
                "Automated citation-resolvability proxy; it does not independently prove source "
                "truth or model faithfulness."
            ),
            "consulting_review": (
                "Automated rubric checks the required brief fields and retrieved multi-hop paths. "
                "Independent human consulting review is pending."
            ),
            "comparison": (
                "Questions with comparison_from run both strict cutoffs. Later-only retrieval is "
                "reported without treating a rank difference as real-world change."
            ),
        },
    }
    output.write_text(
        json.dumps(payload, default=_json_default, indent=2) + "\n", encoding="utf-8"
    )
    _log(
        "evaluation_completed",
        run_id=run_id,
        source="cordis-eurio",
        corpus=CORPUS_ID,
        output=str(output),
        failures=report.has_failures,
        duration_ms=round((monotonic() - started) * 1000),
    )
    print(json.dumps({"output": str(output), "summaries": asdict(report)["summaries"]}, indent=2))
    return 2 if report.has_failures else 0


def _print_result(result: InvestigationResult, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(asdict(result), default=_json_default, indent=2))
        return
    if result.brief is None:
        print(f"Status: {result.status}\n")
        print("Gaps:")
        for gap in result.gaps:
            print(f"- {gap}")
        return
    brief = result.brief
    print(f"# Recommendation\n\n{_format_statement(brief.recommendation)}\n")
    print(f"## Decision\n\n{_format_statement(brief.decision)}\n")
    print("## Supported claims\n")
    for claim in brief.claims:
        print(f"- {_format_statement(claim)}")
    print("\n## Alternatives\n")
    for alternative in brief.alternatives:
        print(f"- {_format_statement(alternative)}")
    print(f"\n## Uncertainty\n\n{_format_statement(brief.uncertainty)}")
    print(f"\n## Next action\n\n{_format_statement(brief.next_action)}")
    if result.gaps:
        print("\n## Gaps\n")
        for gap in result.gaps:
            print(f"- {gap}")


def _print_comparison(comparison: InvestigationComparison, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(asdict(comparison), default=_json_default, indent=2))
        return
    print(
        f"# Evidence change: {comparison.earlier_as_of.isoformat()} to "
        f"{comparison.later_as_of.isoformat()}\n"
    )
    for change in comparison.changes:
        print(f"- {change}")
    print(f"\nEarlier status: {comparison.earlier.status}")
    print(f"Later status: {comparison.later.status}")


def _format_statement(statement: SupportedClaim) -> str:
    references = ", ".join(
        f"[{citation.evidence_id}]({citation.source_url})" for citation in statement.citations
    )
    return f"{statement.text} — {references}"


def _parse_as_of(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _read_evaluation_questions() -> list[dict[str, object]]:
    value = json.loads(Path("evals/questions.json").read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("evals/questions.json must contain a list of question objects")
    return value


def _evaluation_question(value: dict[str, object]) -> EvaluationQuestion:
    try:
        status = value.get("expected_status")
        if status is None:
            expected_status = None
        elif status in {"completed", "abstained"}:
            expected_status = cast(Literal["completed", "abstained"], status)
        else:
            raise ValueError("expected_status must be completed or abstained")
        as_of_value = value.get("as_of")
        comparison_from_value = value.get("comparison_from")
        identifier_values = value.get("reference_identifiers", [])
        path_values = value.get("reference_paths", [])
        support_values = value.get("acceptable_support", [])
        abstain_values = value.get("abstain_when", [])
        invalid_citation_case = value.get("invalid_citation_case")
        if not isinstance(identifier_values, list):
            raise ValueError("reference identifiers must be a list")
        if not isinstance(path_values, list):
            raise ValueError("reference paths must be a list")
        if not isinstance(support_values, list):
            raise ValueError("acceptable support must be a list")
        if not isinstance(abstain_values, list):
            raise ValueError("abstention conditions must be a list")
        if invalid_citation_case is not None and not isinstance(invalid_citation_case, str):
            raise ValueError("invalid_citation_case must be a string")
        return EvaluationQuestion(
            id=str(value["id"]),
            question=str(value["question"]),
            as_of=_parse_as_of(as_of_value if isinstance(as_of_value, str) else None),
            comparison_from=_parse_as_of(
                comparison_from_value if isinstance(comparison_from_value, str) else None
            ),
            reference_identifiers=tuple(str(item) for item in identifier_values),
            reference_paths=tuple(str(item) for item in path_values),
            acceptable_support=tuple(str(item) for item in support_values),
            abstain_when=tuple(str(item) for item in abstain_values),
            invalid_citation_case=invalid_citation_case,
            expected_status=expected_status,
            requires_multihop=bool(value.get("requires_multihop", False)),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid evaluation question configuration") from error


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _log(event: str, **fields: object) -> None:
    record = {"timestamp": datetime.now(UTC).isoformat(), "event": event, **fields}
    print(json.dumps(record, default=_json_default), file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-agentic")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ingest", help="Fetch and ingest the bounded real EURIO seed corpus")
    investigate = subparsers.add_parser(
        "investigate", help="Produce a cited current or historical brief"
    )
    investigate.add_argument("--question", default=CURRENT_QUESTION)
    investigate.add_argument("--as-of", help="ISO cutoff for strict historical eligibility")
    investigate.add_argument("--json", action="store_true", help="Emit the full structured result")
    compare = subparsers.add_parser(
        "compare", help="Compare strict historical briefs at two cutoffs"
    )
    compare.add_argument("--question", default=CURRENT_QUESTION)
    compare.add_argument("--from", dest="earlier_as_of", required=True, help="Earlier ISO cutoff")
    compare.add_argument("--to", dest="later_as_of", required=True, help="Later ISO cutoff")
    compare.add_argument("--json", action="store_true", help="Emit the full structured comparison")
    evaluate = subparsers.add_parser(
        "evaluate", help="Compare the agent with EURIO-only and semantic-only baselines"
    )
    evaluate.add_argument("--output", help="Write the inspectable JSON report to this path")
    return parser
