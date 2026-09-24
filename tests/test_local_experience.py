import gzip
import json
from http.client import HTTPConnection
from threading import Thread
from typing import Any, cast

from kg_agentic.application.cement import LIVE_SEED_PROJECTS
from kg_agentic.knowledge.models import Relationship, StructuralPath
from local_experience.api.conversation import (
    ConversationDecision,
    ConversationModelRequest,
    ConversationRequest,
    ConversationRunner,
)
from local_experience.api.scene import project_graph
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
            "uncertainty": {"text": "Cost evidence is incomplete"},
            "next_action": {"text": "Check site constraints"},
            "claims": [{"text": "A current claim."}],
        },
        "trace": [],
        "gaps": [],
        "asOf": as_of,
    }


def test_projected_map_uses_configured_project_names_for_expanded_corpus() -> None:
    project = LIVE_SEED_PROJECTS[-1]
    paths = (
        StructuralPath(
            relationships=(
                Relationship(
                    subject=project.iri,
                    predicate="http://example.test/hasResult",
                    object="http://example.test/results/123",
                    source_url="https://example.test/source",
                ),
            )
        ),
    )

    nodes, edges = project_graph(paths, ())

    assert next(node for node in nodes if node.id == project.iri).label == (
        f"{project.acronym} · {project.grant_id}"
    )
    assert edges[0].source == project.iri


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
        lambda question, as_of, emit: calls.append((question, as_of))
        or _live_scene(question, as_of),
        decide,
        lambda: {"projectRecords": 6, "sourceVersions": 24},
    )


def test_casual_turn_uses_a_natural_model_reply_without_touching_the_graph() -> None:
    graph_calls: list[tuple[str, str | None]] = []
    model_questions: list[str] = []
    runner = ConversationRunner(
        investigate_live_graph=lambda question, as_of, emit: graph_calls.append((question, as_of))
        or _live_scene(question, as_of),
        conversation_model=lambda request: model_questions.append(request.question)
        or ConversationDecision(action="respond", message="Hi — what are you exploring?"),
        inspect_workspace=lambda: {"projectRecords": 6, "sourceVersions": 24},
    )

    run = runner.run(ConversationRequest("consultant-1", "hi"))

    assert model_questions == ["hi"]
    assert graph_calls == []
    assert run.scene["nodes"] == []
    conversation = cast(dict[str, object], run.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert messages[-1]["content"] == "Hi — what are you exploring?"
    assert conversation["intent"] == "conversation"


def test_runner_exposes_bounded_tools_and_investigates_only_when_selected() -> None:
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

    assert runner.tool_count == 2
    assert runner.tool_names == ("investigate_live_graph", "inspect_workspace")
    assert len(calls) == 2
    assert "Current user question: What should I inspect?" in calls[0][0]
    assert model_requests[1].history[-1]["content"] == (
        "Validate the live result before deciding. Cost evidence is incomplete. "
        "Check site constraints."
    )
    assert [event for event, _ in first.events] == [
        "activity",
        "activity",
        "activity",
        "activity",
        "graph_delta",
    ]
    conversation = cast(dict[str, object], second.scene["conversation"])
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert messages[-1]["content"] == (
        "Validate the live result before deciding. Cost evidence is incomplete. "
        "Check site constraints."
    )


def test_support_activity_identifies_the_sources_used_in_the_answer() -> None:
    scene = _live_scene("What matters?")
    brief = cast(dict[str, object], scene["brief"])
    recommendation = cast(dict[str, object], brief["recommendation"])
    recommendation["citations"] = [{"evidence_id": "current"}]

    events = ConversationRunner._events(scene, "investigation", streamed=True)

    assert events == (("activity", {
        "action": "claim_supported",
        "count": 1,
        "nodeIds": ["evidence:current"],
    }),)


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


def test_workspace_inspection_reads_live_counts_and_the_current_thread_map() -> None:
    calls: list[tuple[str, str | None]] = []
    requests: list[ConversationModelRequest] = []

    def decide(request: ConversationModelRequest) -> ConversationDecision:
        requests.append(request)
        if request.tool_result is not None:
            return ConversationDecision(
                action="respond",
                message="Six project records are indexed; your map has one project and one link.",
            )
        if "inspect" in request.question:
            return ConversationDecision(
                action="investigate", message="", investigation_question="inspect"
            )
        return ConversationDecision(action="inspect", message="")

    runner = ConversationRunner(
        lambda question, as_of, emit: calls.append((question, as_of))
        or _live_scene(question, as_of),
        decide,
        lambda: {"projectRecords": 6, "sourceVersions": 24},
    )
    runner.run(ConversationRequest("one", "inspect a project"))
    inspected = runner.run(ConversationRequest("one", "How many projects are indexed?"))

    assert len(calls) == 1
    assert requests[-1].tool_result == {
        "indexed_corpus": {"projectRecords": 6, "sourceVersions": 24},
        "current_map": {
            "cutoff": None,
            "element_count": 1,
            "link_count": 1,
            "element_types": {"other": 1},
            "link_types": {"other": 1},
            "examples": [],
        },
    }
    assert [event for event, _ in inspected.events] == ["activity"]
    assert inspected.scene["nodes"] == []
    assert cast(dict[str, object], inspected.scene["conversation"])["intent"] == "inspection"
    current_map = cast(dict[str, object], requests[-1].tool_result)["current_map"]
    runner.run(ConversationRequest("one", "How many projects are indexed?", as_of="2020-01-01"))
    assert cast(dict[str, object], requests[-1].tool_result)["current_map"] == current_map
    runner.reset("one")
    runner.run(ConversationRequest("one", "How many projects are indexed?"))
    assert cast(dict[str, object], requests[-1].tool_result)["current_map"] == {
        "cutoff": None,
        "element_count": 0,
        "link_count": 0,
        "element_types": {},
        "link_types": {},
        "examples": [],
    }


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
    assert runner.tool_names == ("investigate_live_graph", "inspect_workspace")


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


def test_health_reports_live_only_tools_and_recorded_route_is_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KG_AGENTIC_DATA_DIR", str(tmp_path))
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
        "corpus": "cement-industrial-decarbonisation-v2",
        "mode": "live-only",
        "toolCount": 2,
        "coverage": {
            "projectRecords": 0,
            "resultMetadataRecords": 0,
            "fullTextRecords": 0,
            "sourceVersions": 0,
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
