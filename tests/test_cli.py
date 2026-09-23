import json
import sys
from pathlib import Path

import pytest

from kg_agentic import cli
from kg_agentic.infrastructure import bootstrap
from kg_agentic.infrastructure.runtime import Settings


class ExternalServiceError(Exception):
    pass


def test_cli_reports_external_service_failure_without_traceback(monkeypatch, capsys) -> None:
    async def fail(_args, **_kwargs):
        raise ExternalServiceError("service quota unavailable")

    monkeypatch.setattr(cli, "_dispatch", fail)
    monkeypatch.setattr(sys, "argv", ["kg-agentic", "ingest"])

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    captured = capsys.readouterr()
    log_line, message = captured.err.splitlines()
    assert stopped.value.code == 1
    record = json.loads(log_line)
    assert record == {
        "timestamp": record["timestamp"],
        "event": "command_failed",
        "run_id": record["run_id"],
        "command": "ingest",
        "source": "cordis-eurio",
        "corpus": "cement-retrofit-v1",
        "duration_ms": record["duration_ms"],
        "error_type": "ExternalServiceError",
    }
    assert "message" not in record
    assert message == "error: service quota unavailable"
    assert "Traceback" not in captured.err


def test_compare_command_accepts_two_historical_cutoffs() -> None:
    args = cli._parser().parse_args(
        [
            "compare",
            "--from",
            "2025-01-01",
            "--to",
            "2027-01-01",
            "--json",
        ]
    )

    assert args.command == "compare"
    assert args.earlier_as_of == "2025-01-01"
    assert args.later_as_of == "2027-01-01"
    assert args.json is True


def test_evaluate_command_accepts_an_explicit_report_path() -> None:
    args = cli._parser().parse_args(["evaluate", "--output", "var/evaluations/report.json"])

    assert args.command == "evaluate"
    assert args.output == "var/evaluations/report.json"


def test_evaluation_question_keeps_support_and_change_configuration() -> None:
    question = cli._evaluation_question(
        {
            "id": "change",
            "question": "What changed?",
            "as_of": "2020-01-01",
            "comparison_from": "2019-01-01",
            "acceptable_support": ["dated public source"],
            "abstain_when": ["No dated evidence"],
            "invalid_citation_case": "Current path used as historical support",
        }
    )

    assert question.comparison_from is not None
    assert question.acceptable_support == ("dated public source",)
    assert question.abstain_when == ("No dated evidence",)
    assert question.invalid_citation_case == "Current path used as historical support"


def test_evaluation_requires_the_committed_frozen_source_versions(tmp_path) -> None:
    expected = json.loads(
        Path("evals/cement-retrofit-v1-baseline.json").read_text(encoding="utf-8")
    )["source_versions"]
    version_path = tmp_path / "cordis-eurio" / "cement-retrofit-v1" / "versions.json"
    version_path.parent.mkdir(parents=True)
    version_path.write_text(json.dumps(expected), encoding="utf-8")
    settings = Settings(
        openai_api_key="test",
        neo4j_uri="bolt://test",
        neo4j_user="neo4j",
        neo4j_password="test",
        neo4j_database="neo4j",
        model="test",
        small_model="test",
        embedding_model="test",
        model_max_output_tokens=1,
        graphiti_max_tokens=1,
        graphiti_max_coroutines=1,
        evidence_limit=1,
        data_dir=tmp_path,
    )

    assert bootstrap.frozen_cement_source_versions(settings) == expected

    version_path.write_text(json.dumps(["different-version"]), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match the frozen"):
        bootstrap.frozen_cement_source_versions(settings)
