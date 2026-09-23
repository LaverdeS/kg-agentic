import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any, cast

from local_experience.api.conversation import ConversationRequest, ConversationRunner
from local_experience.api.server import ExplorerHandler


def _live_scene(question: str, as_of: str | None = None) -> dict[str, object]:
    return {
        "question": question,
        "status": "completed",
        "mode": "live",
        "nodes": [{"id": "project:current", "label": "Current project"}],
        "edges": [
            {"id": "path:current", "source": "project:current", "target": "evidence:current"}
        ],
        "evidence": [{"id": "current", "nodeId": "evidence:current"}],
        "brief": {
            "recommendation": {"text": "Validate the live result before deciding."},
            "claims": [{"text": "A current claim."}],
        },
        "trace": [],
        "gaps": [],
        "asOf": as_of,
    }


def _runner(calls: list[tuple[str, str | None]]) -> ConversationRunner:
    return ConversationRunner(
        lambda question, as_of: calls.append((question, as_of)) or _live_scene(question, as_of),
        lambda: {"ready": True, "summary": "Live graph credentials are present."},
        lambda: ("Test a live decision question.",) * 6,
    )


def test_runner_binds_three_tools_and_investigates_live_every_time() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(calls)

    first = runner.run(ConversationRequest("consultant-1", "What should I inspect?"))
    second = runner.run(ConversationRequest("consultant-1", "What changes the decision?"))

    assert runner.tool_count == 3
    assert runner.tool_names == (
        "check_live_services",
        "recommend_test_tasks",
        "investigate_live_graph",
    )
    assert len(calls) == 2
    assert "Use a live tool before answering" in calls[0][0]
    assert "Earlier question for context only" in calls[1][0]
    assert [event for event, _ in first.events] == [
        "activity",
        "activity",
        "activity",
        "graph_delta",
    ]
    conversation = cast(dict[str, object], second.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert messages[-1]["content"] == "Validate the live result before deciding."


def test_help_uses_live_tools_and_never_invents_a_graph() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(calls)

    run = runner.run(
        ConversationRequest("consultant-1", "What is this app and what tools do you use?")
    )

    assert calls == []
    assert run.scene["nodes"] == []
    assert run.scene["evidence"] == []
    assert [event for event, _ in run.events] == ["activity"]
    conversation = cast(dict[str, object], run.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert "not a recorded example" in messages[-1]["content"]
    assert "1. Test a live decision question." in messages[-1]["content"]


def test_requesting_examples_recommends_multiple_live_test_tasks() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(calls)

    run = runner.run(ConversationRequest("consultant-1", "What examples can I try to test this?"))

    assert calls == []
    messages = cast(
        list[dict[str, str]], cast(dict[str, object], run.scene["conversation"])["messages"]
    )
    assert "1. Test a live decision question." in messages[-1]["content"]
    assert "5. Test a live decision question." in messages[-1]["content"]


def test_selected_ui_context_and_historical_cutoff_are_sent_to_new_live_run() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(calls)

    run = runner.run(
        ConversationRequest(
            "consultant-1",
            "What did the evidence support?",
            selected_node_ids=("evidence:current",),
            as_of="2020-01-01",
        )
    )

    assert calls[0][1] == "2020-01-01"
    assert "Selected UI context, not evidence: evidence:current" in calls[0][0]
    conversation = cast(dict[str, object], run.scene["conversation"])
    assert conversation["selectedNodeIds"] == ["evidence:current"]


def test_threads_are_isolated_and_resettable_without_retaining_results() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(calls)

    first = runner.run(ConversationRequest("one", "What should I inspect?"))
    follow_up = runner.run(ConversationRequest("one", "What changes the decision?"))
    separate = runner.run(ConversationRequest("two", "What should I inspect?"))
    runner.reset("one")
    reset = runner.run(ConversationRequest("one", "Start over."))

    first_conversation = cast(dict[str, object], first.scene["conversation"])
    follow_up_conversation = cast(dict[str, object], follow_up.scene["conversation"])
    separate_conversation = cast(dict[str, object], separate.scene["conversation"])
    reset_conversation = cast(dict[str, object], reset.scene["conversation"])
    assert len(cast(list[object], first_conversation["messages"])) == 2
    assert len(cast(list[object], follow_up_conversation["messages"])) == 4
    assert len(cast(list[object], separate_conversation["messages"])) == 2
    assert len(cast(list[object], reset_conversation["messages"])) == 2
    assert len(calls) == 4


def test_health_reports_live_only_tools_and_recorded_route_is_absent() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ExplorerHandler)
    worker = Thread(target=server.handle_request)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        health = json.loads(response.read())
    finally:
        connection.close()
        worker.join(timeout=1)
        server.server_close()

    assert response.status == 200
    assert health == {
        "status": "ready",
        "corpus": "cement-retrofit-v1",
        "mode": "live-only",
        "toolCount": 3,
    }

    server = ThreadingHTTPServer(("127.0.0.1", 0), ExplorerHandler)
    worker = Thread(target=server.handle_request)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request("GET", "/api/scene/recorded")
        response = connection.getresponse()
        payload = cast(dict[str, Any], json.loads(response.read()))
    finally:
        connection.close()
        worker.join(timeout=1)
        server.server_close()

    assert response.status == 404
    assert "No local-experience endpoint" in payload["error"]
