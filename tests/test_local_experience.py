import gzip
import json
from http.client import HTTPConnection
from threading import Thread
from typing import Any, cast

from local_experience.api.conversation import (
    ConversationDecision,
    ConversationModelRequest,
    ConversationRequest,
    ConversationRunner,
)
from local_experience.api.server import ExplorerHandler, ExplorerServer


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


def _runner(
    calls: list[tuple[str, str | None]],
    decisions: list[ConversationDecision],
    model_requests: list[ConversationModelRequest] | None = None,
) -> ConversationRunner:
    remaining = iter(decisions)

    def decide(request: ConversationModelRequest) -> ConversationDecision:
        if model_requests is not None:
            model_requests.append(request)
        return next(remaining)

    return ConversationRunner(
        lambda question, as_of: calls.append((question, as_of)) or _live_scene(question, as_of),
        decide,
    )


def test_casual_turn_uses_a_natural_model_reply_without_touching_the_graph() -> None:
    graph_calls: list[tuple[str, str | None]] = []
    model_questions: list[str] = []
    runner = ConversationRunner(
        investigate_live_graph=lambda question, as_of: graph_calls.append((question, as_of))
        or _live_scene(question, as_of),
        conversation_model=lambda request: model_questions.append(request.question)
        or ConversationDecision(action="respond", message="Hi — what are you exploring?"),
    )

    run = runner.run(ConversationRequest("consultant-1", "hi"))

    assert model_questions == ["hi"]
    assert graph_calls == []
    assert run.scene["nodes"] == []
    conversation = cast(dict[str, object], run.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert messages[-1]["content"] == "Hi — what are you exploring?"
    assert conversation["intent"] == "conversation"


def test_runner_exposes_one_bounded_tool_and_investigates_only_when_selected() -> None:
    calls: list[tuple[str, str | None]] = []
    model_requests: list[ConversationModelRequest] = []
    runner = _runner(
        calls,
        [
            ConversationDecision(
                action="investigate",
                message="I’ll check the evidence.",
                investigation_question="What should I inspect?",
            ),
            ConversationDecision(
                action="investigate",
                message="I’ll check what could change it.",
                investigation_question="What changes the decision?",
            ),
        ],
        model_requests,
    )

    first = runner.run(ConversationRequest("consultant-1", "What should I inspect?"))
    second = runner.run(ConversationRequest("consultant-1", "What changes the decision?"))

    assert runner.tool_count == 1
    assert runner.tool_names == ("investigate_live_graph",)
    assert len(calls) == 2
    assert "Current user question: What should I inspect?" in calls[0][0]
    assert model_requests[1].history[-1]["content"] == "Validate the live result before deciding."
    assert [event for event, _ in first.events] == [
        "activity",
        "activity",
        "activity",
        "activity",
        "graph_delta",
    ]
    conversation = cast(dict[str, object], second.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert messages[-1]["content"] == "Validate the live result before deciding."


def test_explanation_uses_the_model_reply_and_never_invents_a_graph() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(
        calls,
        [
            ConversationDecision(
                action="respond",
                message="A retrofit adapts an existing plant instead of building a new one.",
            )
        ],
    )

    run = runner.run(ConversationRequest("consultant-1", "What is retrofit?"))

    assert calls == []
    assert run.scene["nodes"] == []
    assert run.scene["evidence"] == []
    assert [event for event, _ in run.events] == ["activity"]
    conversation = cast(dict[str, object], run.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert messages[-1]["content"].startswith("A retrofit adapts")
    assert cast(dict[str, object], run.scene["conversation"])["intent"] == "conversation"


def test_requesting_examples_gets_model_guidance_without_an_example_tool() -> None:
    calls: list[tuple[str, str | None]] = []
    runner = _runner(
        calls,
        [
            ConversationDecision(
                action="respond",
                message=(
                    "Try comparing retrofit evidence, tracing a partner path, or checking a cutoff."
                ),
            )
        ],
    )

    run = runner.run(ConversationRequest("consultant-1", "What examples can I try to test this?"))

    assert calls == []
    messages = cast(
        list[dict[str, str]], cast(dict[str, object], run.scene["conversation"])["messages"]
    )
    assert "partner path" in messages[-1]["content"]
    assert runner.tool_names == ("investigate_live_graph",)


def test_explicit_graph_opt_out_is_a_hard_tool_constraint() -> None:
    calls: list[tuple[str, str | None]] = []
    model_requests: list[ConversationModelRequest] = []
    runner = _runner(
        calls,
        [
            ConversationDecision(
                action="investigate",
                message="Without the graph: retrofit means adapting an existing asset.",
                investigation_question="What is retrofit?",
            )
        ],
        model_requests,
    )

    run = runner.run(ConversationRequest("consultant-1", "What is retrofit? Do not use the graph."))

    assert model_requests[0].retrieval_allowed is False
    assert calls == []
    conversation = cast(dict[str, object], run.scene["conversation"])
    assert conversation["intent"] == "conversation"


def test_selected_ui_context_and_historical_cutoff_are_sent_to_new_live_run() -> None:
    calls: list[tuple[str, str | None]] = []
    model_requests: list[ConversationModelRequest] = []
    runner = _runner(
        calls,
        [
            ConversationDecision(
                action="investigate",
                message="I’ll check that context.",
                investigation_question="What did the evidence support?",
            )
        ],
        model_requests,
    )

    run = runner.run(
        ConversationRequest(
            "consultant-1",
            "What did the evidence support?",
            selected_node_ids=("evidence:current",),
            as_of="2020-01-01",
        )
    )

    assert calls[0][1] == "2020-01-01"
    assert "Selected interface context, not evidence: evidence:current" in calls[0][0]
    assert model_requests[0].selected_node_ids == ("evidence:current",)
    conversation = cast(dict[str, object], run.scene["conversation"])
    assert conversation["selectedNodeIds"] == ["evidence:current"]


def test_threads_are_isolated_and_resettable_without_retaining_results() -> None:
    calls: list[tuple[str, str | None]] = []
    model_requests: list[ConversationModelRequest] = []
    runner = _runner(
        calls,
        [
            ConversationDecision(action="respond", message="First."),
            ConversationDecision(action="respond", message="Follow-up."),
            ConversationDecision(action="respond", message="Separate."),
            ConversationDecision(action="respond", message="Reset."),
        ],
        model_requests,
    )

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
    assert calls == []
    assert [len(request.history) for request in model_requests] == [0, 2, 0, 0]


def test_health_reports_live_only_tools_and_recorded_route_is_absent() -> None:
    server = ExplorerServer(("127.0.0.1", 0), ExplorerHandler)
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
        "toolCount": 1,
        "coverage": {
            "projectRecords": 3,
            "resultMetadataRecords": 6,
                "fullTextRecords": 2,
                "sourceVersions": 11,
        },
    }

    server = ExplorerServer(("127.0.0.1", 0), ExplorerHandler)
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


def test_client_assets_declare_their_content_length() -> None:
    server = ExplorerServer(("127.0.0.1", 0), ExplorerHandler)
    worker = Thread(target=server.handle_request)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()
        worker.join(timeout=1)
        server.server_close()

    assert response.status == 200
    assert response.getheader("Content-Length") == str(len(body))


def test_client_assets_use_gzip_when_the_browser_accepts_it() -> None:
    server = ExplorerServer(("127.0.0.1", 0), ExplorerHandler)
    worker = Thread(target=server.handle_request)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request("GET", "/", headers={"Accept-Encoding": "gzip"})
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()
        worker.join(timeout=1)
        server.server_close()

    assert response.getheader("Content-Encoding") == "gzip"
    assert b"Evidence Workbench" in gzip.decompress(body)
