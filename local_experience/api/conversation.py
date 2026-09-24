"""Conversation orchestration for the live local evidence workspace.

The language model may converse, navigate existing UI context, or request one
bounded core investigation. Only the last option can call the evidence graph.
"""

from __future__ import annotations

import operator
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict, cast

from langgraph.graph import START, StateGraph

from kg_agentic.application.conversation import (
    ConversationDecision,
    ConversationModel,
    ConversationModelRequest,
)

INVESTIGATION_CONTEXT = """Run a bounded evidence investigation for the current user question.
Use EURIO structural relationships and the configured Graphiti evidence corpus. Keep structural
relationships separate from source claims, make uncertainty explicit, and never turn project
participation, objectives, or missing data into proof."""

Intent = Literal["investigation", "navigation", "conversation", "inspection"]
EventEmitter = Callable[[str, dict[str, object]], None]
SceneLoader = Callable[[str, str | None, EventEmitter | None], dict[str, object]]
WorkspaceLoader = Callable[[], dict[str, int]]


class ConversationState(TypedDict, total=False):
    question: str
    thread_id: str
    selected_node_ids: list[str]
    as_of: str | None
    intent: Intent
    decision: ConversationDecision
    scene: dict[str, object]
    inspection: dict[str, object]
    on_event: EventEmitter | None
    history: Annotated[list[dict[str, str]], operator.add]


@dataclass(frozen=True)
class ConversationRequest:
    thread_id: str
    question: str
    selected_node_ids: tuple[str, ...] = ()
    as_of: str | None = None


@dataclass(frozen=True)
class ConversationRun:
    events: tuple[tuple[str, dict[str, object]], ...]
    scene: dict[str, object]


class ConversationRunner:
    """Keep natural conversation and bounded evidence investigation behind one interface."""

    tool_names = ("investigate_live_graph", "inspect_workspace")

    def __init__(
        self,
        investigate_live_graph: SceneLoader,
        conversation_model: ConversationModel,
        inspect_workspace: WorkspaceLoader,
    ) -> None:
        self._investigate_live_graph = investigate_live_graph
        self._conversation_model = conversation_model
        self._inspect_workspace = inspect_workspace
        self._history_by_thread: dict[str, list[dict[str, str]]] = {}
        self._map_by_thread: dict[str, dict[str, object]] = {}
        workflow = StateGraph(ConversationState)
        workflow.add_node("reason", self._reason)
        workflow.add_node("act", self._act)
        workflow.add_node("respond", self._respond)
        workflow.add_edge(START, "reason")
        workflow.add_edge("reason", "act")
        workflow.add_edge("act", "respond")
        self._graph = workflow.compile()

    @property
    def tool_count(self) -> int:
        return len(self.tool_names)

    def run(
        self, request: ConversationRequest, *, on_event: EventEmitter | None = None
    ) -> ConversationRun:
        question = request.question.strip()
        if not question:
            raise ValueError("question must be a non-empty string")
        if not request.thread_id.strip():
            raise ValueError("threadId must be a non-empty string")

        state = cast(
            ConversationState,
            self._graph.invoke(
                {
                    "question": question,
                    "selected_node_ids": list(request.selected_node_ids),
                    "as_of": request.as_of,
                    "thread_id": request.thread_id,
                    "on_event": on_event,
                    "history": self._history_by_thread.get(request.thread_id, []),
                },
            ),
        )
        intent = cast(Intent, state.get("intent"))
        decision = cast(ConversationDecision, state.get("decision"))
        scene = dict(cast(dict[str, object], state.get("scene")))
        scene["question"] = question
        scene["conversation"] = {
            "threadId": request.thread_id,
            "selectedNodeIds": list(request.selected_node_ids),
            "messages": state.get("history", [])[-8:],
            "asOf": request.as_of,
            "intent": intent,
            "navigationTarget": decision.navigation_target,
        }
        self._history_by_thread[request.thread_id] = cast(
            list[dict[str, str]], state.get("history", [])[-8:]
        )
        if intent == "investigation":
            self._remember_map(request.thread_id, request.as_of, scene)
        return ConversationRun(
            events=self._events(scene, intent, streamed=on_event is not None), scene=scene
        )

    def reset(self, thread_id: str) -> None:
        if not thread_id.strip():
            raise ValueError("threadId must be a non-empty string")
        self._history_by_thread.pop(thread_id, None)
        self._map_by_thread.pop(thread_id, None)

    def _reason(self, state: ConversationState) -> ConversationState:
        question = cast(str, state.get("question"))
        retrieval_allowed = not _retrieval_opted_out(question)
        decision = self._conversation_model(
            ConversationModelRequest(
                question=question,
                history=tuple(state.get("history", [])),
                selected_node_ids=tuple(state.get("selected_node_ids", [])),
                as_of=state.get("as_of"),
                retrieval_allowed=retrieval_allowed,
            )
        )
        action = decision.action
        if action in {"investigate", "inspect"} and not retrieval_allowed:
            action = "respond"
            decision = ConversationDecision(action="respond", message=decision.message)
        intent: Intent = (
            "investigation"
            if action == "investigate"
            else "navigation"
            if action == "navigate"
            else "inspection"
            if action == "inspect"
            else "conversation"
        )
        return {
            "intent": intent,
            "decision": decision,
            "history": [{"role": "user", "content": question}],
        }

    def _act(self, state: ConversationState) -> ConversationState:
        intent = cast(Intent, state.get("intent"))
        if intent == "inspection":
            thread_id = cast(str, state.get("thread_id"))
            map_state = self._map_by_thread.get(thread_id)
            return {
                "scene": _empty_scene(),
                "inspection": {
                    "indexed_corpus": self._inspect_workspace(),
                    "current_map": _map_summary(map_state),
                },
            }
        if intent != "investigation":
            return {"scene": _empty_scene()}
        decision = cast(ConversationDecision, state.get("decision"))
        on_event = state.get("on_event")
        if on_event is not None:
            on_event(
                "activity",
                {"action": "planned", "detail": "Checking live relationships and public sources."},
            )
        return {
            "scene": self._investigate_live_graph(
                _investigation_query(
                    decision.investigation_question or cast(str, state.get("question")),
                    cast(list[str], state.get("selected_node_ids", [])),
                ),
                state.get("as_of"),
                on_event,
            )
        }

    def _respond(self, state: ConversationState) -> ConversationState:
        intent = cast(Intent, state.get("intent"))
        if intent == "inspection":
            result = self._conversation_model(
                ConversationModelRequest(
                    question=cast(str, state.get("question")),
                    history=tuple(state.get("history", [])[:-1]),
                    selected_node_ids=tuple(state.get("selected_node_ids", [])),
                    as_of=state.get("as_of"),
                    retrieval_allowed=False,
                    tool_result=cast(dict[str, object], state.get("inspection")),
                )
            )
            if result.action != "respond":
                raise RuntimeError("The workspace inspection did not produce an answer.")
            response = result.message
        elif intent == "investigation":
            scene = cast(dict[str, object], state.get("scene"))
            brief = cast(dict[str, object] | None, scene.get("brief"))
            if brief is None:
                response = (
                    "The available public evidence does not support a defensible "
                    "recommendation yet. "
                    "See the research gaps for what needs checking next."
                )
            else:
                recommendation = cast(dict[str, object], brief["recommendation"])
                uncertainty = cast(dict[str, object], brief["uncertainty"])
                next_action = cast(dict[str, object], brief["next_action"])
                response = " ".join(
                    part for part in (
                        _sentence(cast(str, recommendation["text"])),
                        _sentence(cast(str, uncertainty["text"])),
                        _sentence(cast(str, next_action["text"])),
                    ) if part
                )
        else:
            decision = cast(ConversationDecision, state.get("decision"))
            response = decision.message
        return {"history": [{"role": "assistant", "content": response}]}

    @staticmethod
    def _events(
        scene: dict[str, object], intent: Intent, *, streamed: bool = False
    ) -> tuple[tuple[str, dict[str, object]], ...]:
        if intent == "conversation":
            return (("activity", {"action": "answered", "detail": "No evidence tools used."}),)
        if intent == "navigation":
            return (("activity", {"action": "focused", "detail": "Existing graph only."}),)
        if intent == "inspection":
            return (
                (
                    "activity",
                    {"action": "inspected", "detail": "Read current workspace counts and map."},
                ),
            )
        nodes = cast(list[dict[str, object]], scene["nodes"])
        evidence = cast(list[dict[str, object]], scene["evidence"])
        brief = cast(dict[str, object] | None, scene.get("brief"))
        claim_count = len(cast(list[object], brief.get("claims", []))) if brief else 0
        support_event = {
            "action": "claim_supported",
            "count": claim_count,
            "nodeIds": _supported_evidence_node_ids(brief),
        }
        if streamed:
            return (("activity", support_event),)
        return (
            (
                "activity",
                {
                    "action": "planned",
                    "detail": "Starting a live evidence investigation for this question.",
                },
            ),
            (
                "activity",
                {"action": "retrieved_path", "count": len(cast(list[object], scene["edges"]))},
            ),
            ("activity", {"action": "evidence_found", "count": len(evidence)}),
            ("activity", support_event),
            ("graph_delta", {"nodes": nodes, "edges": scene["edges"]}),
        )

    def _remember_map(self, thread_id: str, as_of: str | None, scene: dict[str, object]) -> None:
        previous = self._map_by_thread.get(thread_id)
        if previous is None or previous["as_of"] != as_of:
            previous = {"as_of": as_of, "nodes": {}, "edges": {}}
        nodes = cast(dict[str, dict[str, object]], previous["nodes"])
        edges = cast(dict[str, dict[str, object]], previous["edges"])
        for node in cast(list[dict[str, object]], scene["nodes"]):
            nodes[cast(str, node["id"])] = node
        for edge in cast(list[dict[str, object]], scene["edges"]):
            edges[cast(str, edge["id"])] = edge
        self._map_by_thread[thread_id] = previous


def _empty_scene() -> dict[str, object]:
    return {
        "question": "",
        "status": "ready",
        "mode": "live",
        "nodes": [],
        "edges": [],
        "evidence": [],
        "brief": None,
        "trace": [],
        "gaps": [],
    }


def _map_summary(map_state: dict[str, object] | None) -> dict[str, object]:
    if map_state is None:
        return {
            "cutoff": None,
            "element_count": 0,
            "link_count": 0,
            "element_types": {},
            "link_types": {},
            "examples": [],
        }
    nodes = cast(dict[str, dict[str, object]], map_state["nodes"])
    edges = cast(dict[str, dict[str, object]], map_state["edges"])
    examples = [
        {"label": node.get("label"), "type": node.get("kind")}
        for node in nodes.values()
        if node.get("kind") in {"project", "organization", "output"}
    ][:20]
    return {
        "cutoff": map_state["as_of"],
        "element_count": len(nodes),
        "link_count": len(edges),
        "element_types": dict(Counter(str(node.get("kind", "other")) for node in nodes.values())),
        "link_types": dict(Counter(str(edge.get("label", "other")) for edge in edges.values())),
        "examples": examples,
    }


def _retrieval_opted_out(question: str) -> bool:
    normalized = " ".join(question.casefold().split())
    return bool(
        re.search(
            r"\b(do not|don't|dont|without|no)\s+(use|using|search|query|check)?\s*"
            r"(the\s+)?(graph|retrieval|tools?|evidence)\b",
            normalized,
        )
    )


def _investigation_query(question: str, selected_node_ids: list[str]) -> str:
    context = [INVESTIGATION_CONTEXT]
    if selected_node_ids:
        context.append(
            "Selected interface context, not evidence: " + ", ".join(selected_node_ids)
        )
    context.append(f"Current user question: {question}")
    return "\n\n".join(context)


def _sentence(text: str) -> str:
    """Keep supported brief text readable when composing the conversational answer."""
    clean = " ".join(text.split()).strip()
    if not clean:
        return ""
    return clean if clean[-1] in ".!?" else f"{clean}."


def _supported_evidence_node_ids(brief: dict[str, object] | None) -> list[str]:
    if brief is None:
        return []
    statements = [
        brief.get(key)
        for key in ("decision", "recommendation", "uncertainty", "next_action")
    ]
    statements.extend(cast(list[object], brief.get("alternatives", [])))
    statements.extend(cast(list[object], brief.get("claims", [])))
    ids: set[str] = set()
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        for citation in cast(list[dict[str, object]], statement.get("citations", [])):
            evidence_id = citation.get("evidence_id")
            if isinstance(evidence_id, str):
                ids.add(f"evidence:{evidence_id}")
    return sorted(ids)
