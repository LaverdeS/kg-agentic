import json
import sys

import pytest

from kg_agentic import cli


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
