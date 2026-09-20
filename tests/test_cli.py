import json
import sys

import pytest

from kg_agentic import cli


class ExternalServiceError(Exception):
    pass


def test_cli_reports_external_service_failure_without_traceback(monkeypatch, capsys) -> None:
    async def fail(_args):
        raise ExternalServiceError("service quota unavailable")

    monkeypatch.setattr(cli, "_dispatch", fail)
    monkeypatch.setattr(sys, "argv", ["kg-agentic", "ingest"])

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    captured = capsys.readouterr()
    log_line, message = captured.err.splitlines()
    assert stopped.value.code == 1
    assert json.loads(log_line)["error_type"] == "ExternalServiceError"
    assert message == "error: service quota unavailable"
    assert "Traceback" not in captured.err
