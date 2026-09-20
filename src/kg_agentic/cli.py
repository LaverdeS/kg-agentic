import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from time import monotonic
from uuid import uuid4

from dotenv import load_dotenv

from kg_agentic.application.cement import CORPUS_ID, CURRENT_QUESTION
from kg_agentic.infrastructure.bootstrap import ingest_cement_slice, investigate_cement_slice
from kg_agentic.infrastructure.runtime import Settings
from kg_agentic.knowledge.models import InvestigationRequest, InvestigationResult, SupportedClaim


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
    if args.command == "evaluate":
        questions = json.loads(Path("evals/questions.json").read_text(encoding="utf-8"))
        print(json.dumps(questions, indent=2))
        return 0
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
    investigate = subparsers.add_parser("investigate", help="Produce a cited current brief")
    investigate.add_argument("--question", default=CURRENT_QUESTION)
    investigate.add_argument("--as-of", help="ISO date; rejected until historical mode exists")
    investigate.add_argument("--json", action="store_true", help="Emit the full structured result")
    subparsers.add_parser("evaluate", help="Print the initial evaluation questions")
    return parser
