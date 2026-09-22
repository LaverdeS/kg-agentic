import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any, cast

from local_experience.api.conversation import ConversationRequest, ConversationRunner
from local_experience.api.recorded import recorded_result
from local_experience.api.scene import project_scene, scene_payload
from local_experience.api.server import ExplorerHandler


def test_recorded_scene_preserves_source_qualified_graph_and_citations() -> None:
    scene = project_scene(recorded_result(), mode="recorded")
    payload = scene_payload(scene)

    assert scene.mode == "recorded"
    assert {node.kind for node in scene.nodes} >= {"project", "organization", "output", "evidence"}
    assert all(edge.source_url for edge in scene.edges)
    evidence = cast(list[dict[str, object]], payload["evidence"])
    brief = cast(dict[str, object], payload["brief"])
    recommendation = cast(dict[str, object], brief["recommendation"])
    citations = cast(list[dict[str, object]], recommendation["citations"])
    assert len(evidence) == 4
    deliverable = next(
        item for item in evidence if item["sourceCategory"] == "public_deliverable_full_text"
    )
    assert "CEMCAP D4.5" in cast(str, deliverable["text"])
    assert "zenodo.org/records/2593240" in cast(str, deliverable["sourceUrl"])
    assert cast(str, citations[0]["evidence_id"]).startswith(
        "publication:"
    )


def test_recorded_scene_is_current_only_and_does_not_claim_live_data() -> None:
    scene = project_scene(recorded_result(), mode="recorded")

    assert scene.gaps == (
        "This recorded UX snapshot is current-only; historical requests remain unsupported.",
    )
    assert scene.status == "completed"


def test_recorded_conversation_streams_public_stages_and_keeps_selected_context() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ExplorerHandler)
    worker = Thread(target=server.handle_request)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    request = {
        "mode": "recorded",
        "question": "Which CEMCAP evidence should I inspect next?",
        "threadId": "consultant-1",
        "selectedNodeIds": ["evidence:publication:perez-calvo-2018:recorded"],
    }

    try:
        connection.request(
            "POST",
            "/api/conversations",
            body=json.dumps(request),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = response.read().decode()
    finally:
        connection.close()
        worker.join(timeout=1)
        server.server_close()

    assert response.status == 200
    events = _sse_events(payload)
    assert [event["event"] for event in events] == [
        "run_started",
        "activity",
        "activity",
        "activity",
        "activity",
        "graph_delta",
        "completed",
    ]
    assert [event["data"]["action"] for event in events[1:5]] == [
        "planned",
        "retrieved_path",
        "evidence_found",
        "claim_supported",
    ]
    assert events[-1]["data"]["conversation"]["threadId"] == "consultant-1"
    assert events[-1]["data"]["conversation"]["selectedNodeIds"] == request["selectedNodeIds"]


def test_recorded_conversation_rejects_a_historical_cutoff() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ExplorerHandler)
    worker = Thread(target=server.handle_request)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)

    try:
        connection.request(
            "POST",
            "/api/conversations",
            body=json.dumps(
                {
                    "mode": "recorded",
                    "question": "What was known in 2019?",
                    "threadId": "consultant-1",
                    "asOf": "2019-01-01",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
    finally:
        connection.close()
        worker.join(timeout=1)
        server.server_close()

    assert response.status == 400
    assert payload == {"error": "An asOf date requires a live investigation."}


def test_help_question_does_not_run_retrieval_or_change_the_graph() -> None:
    retrieved_questions: list[str] = []
    runner = ConversationRunner(
        lambda question, mode, as_of: retrieved_questions.append(question) or {},
        lambda: scene_payload(project_scene(recorded_result(), mode="recorded")),
    )

    run = runner.run(
        ConversationRequest("consultant-1", "What is this app and what data can it use?", "live")
    )

    assert retrieved_questions == []
    assert [event for event, _ in run.events] == []
    conversation = cast(dict[str, object], run.scene["conversation"])
    assert conversation["intent"] == "help"
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert "does not search or change the graph" in messages[-1]["content"]


def test_casual_turn_stays_in_the_local_conversation_without_retrieval() -> None:
    retrieved_questions: list[str] = []
    runner = ConversationRunner(
        lambda question, mode, as_of: retrieved_questions.append(question) or {},
        lambda: scene_payload(project_scene(recorded_result(), mode="recorded")),
    )

    run = runner.run(ConversationRequest("consultant-1", "Hello there", "recorded"))

    assert retrieved_questions == []
    assert [event for event, _ in run.events] == []
    conversation = cast(dict[str, object], run.scene["conversation"])
    assert conversation["intent"] == "conversation"
    messages = cast(list[dict[str, str]], conversation["messages"])
    assert "No evidence retrieval has started" in messages[-1]["content"]

    thanks = runner.run(ConversationRequest("consultant-1", "Thanks, that helps.", "recorded"))
    recap = runner.run(ConversationRequest("consultant-1", "Can you recap?", "recorded"))

    assert retrieved_questions == []
    assert cast(dict[str, object], thanks.scene["conversation"])["intent"] == "conversation"
    recap_conversation = cast(dict[str, object], recap.scene["conversation"])
    recap_messages = cast(list[dict[str, str]], recap_conversation["messages"])
    assert "Thanks, that helps." in recap_messages[-1]["content"]


def test_navigation_question_focuses_a_known_element_without_retrieval() -> None:
    retrieved_questions: list[str] = []
    runner = ConversationRunner(
        lambda question, mode, as_of: retrieved_questions.append(question) or {},
        lambda: scene_payload(project_scene(recorded_result(), mode="recorded")),
    )

    run = runner.run(ConversationRequest("consultant-1", "Focus CEMCAP D4.5", "recorded"))

    assert retrieved_questions == []
    assert [event for event, _ in run.events] == []
    conversation = cast(dict[str, object], run.scene["conversation"])
    assert conversation["intent"] == "navigation"
    assert conversation["navigationTarget"] == "evidence:deliverable:cemcap-d4.5-v1:recorded"


def test_conversation_threads_are_isolated_and_resettable() -> None:
    runner = ConversationRunner(
        lambda question, mode, as_of: {
            **scene_payload(project_scene(recorded_result(), mode=mode)),
            "question": question,
        },
        lambda: scene_payload(project_scene(recorded_result(), mode="recorded")),
    )

    first = runner.run(ConversationRequest("one", "What should I inspect?", "recorded"))
    follow_up = runner.run(
        ConversationRequest("one", "What changes the recommendation?", "recorded")
    )
    separate = runner.run(ConversationRequest("two", "What should I inspect?", "recorded"))
    runner.reset("one")
    reset = runner.run(ConversationRequest("one", "Start over.", "recorded"))

    assert len(cast(dict[str, list[object]], first.scene["conversation"])["messages"]) == 2
    assert len(cast(dict[str, list[object]], follow_up.scene["conversation"])["messages"]) == 4
    assert len(cast(dict[str, list[object]], separate.scene["conversation"])["messages"]) == 2
    assert len(cast(dict[str, list[object]], reset.scene["conversation"])["messages"]) == 2


def _sse_events(payload: str) -> list[dict[str, Any]]:
    return [
        {
            "event": block.removeprefix("event: ").split("\n", maxsplit=1)[0],
            "data": json.loads(block.split("data: ", maxsplit=1)[1]),
        }
        for block in payload.strip().split("\n\n")
    ]
