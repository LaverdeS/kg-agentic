"""Conversation orchestration for the live local evidence workspace.

The language model may converse, navigate existing UI context, or request one
bounded core investigation. Only the last option can call the evidence graph.
"""

from __future__ import annotations

import operator
import re
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

Intent = Literal["investigation", "navigation", "conversation"]
SceneLoader = Callable[[str, str | None], dict[str, object]]


class ConversationState(TypedDict, total=False):
    question: str
    selected_node_ids: list[str]
    as_of: str | None
    intent: Intent
    decision: ConversationDecision
    scene: dict[str, object]
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

    tool_names = ("investigate_live_graph",)

    def __init__(
        self,
        investigate_live_graph: SceneLoader,
        conversation_model: ConversationModel,
    ) -> None:
        self._investigate_live_graph = investigate_live_graph
        self._conversation_model = conversation_model
        self._history_by_thread: dict[str, list[dict[str, str]]] = {}
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

    def run(self, request: ConversationRequest) -> ConversationRun:
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
        return ConversationRun(events=self._events(scene, intent), scene=scene)

    def reset(self, thread_id: str) -> None:
        if not thread_id.strip():
            raise ValueError("threadId must be a non-empty string")
        self._history_by_thread.pop(thread_id, None)

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
        if action == "investigate" and not retrieval_allowed:
            action = "respond"
            decision = ConversationDecision(action="respond", message=decision.message)
        intent: Intent = (
            "investigation"
            if action == "investigate"
            else "navigation"
            if action == "navigate"
            else "conversation"
        )
        return {
            "intent": intent,
            "decision": decision,
            "history": [{"role": "user", "content": question}],
        }

    def _act(self, state: ConversationState) -> ConversationState:
        intent = cast(Intent, state.get("intent"))
        if intent != "investigation":
            return {"scene": _empty_scene()}
        decision = cast(ConversationDecision, state.get("decision"))
        return {
            "scene": self._investigate_live_graph(
                _investigation_query(
                    decision.investigation_question or cast(str, state.get("question")),
                    cast(list[str], state.get("selected_node_ids", [])),
                ),
                state.get("as_of"),
            )
        }

    def _respond(self, state: ConversationState) -> ConversationState:
        intent = cast(Intent, state.get("intent"))
        if intent == "investigation":
            scene = cast(dict[str, object], state.get("scene"))
            brief = cast(dict[str, object] | None, scene.get("brief"))
            if brief is None:
                response = (
                    "I checked the live evidence, but it could not support a recommendation. "
                    "The workspace shows the gaps to validate next."
                )
            else:
                recommendation = cast(dict[str, object], brief["recommendation"])
                response = cast(str, recommendation["text"])
        else:
            decision = cast(ConversationDecision, state.get("decision"))
            response = decision.message
        return {"history": [{"role": "assistant", "content": response}]}

    @staticmethod
    def _events(
        scene: dict[str, object], intent: Intent
    ) -> tuple[tuple[str, dict[str, object]], ...]:
        if intent == "conversation":
            return (("activity", {"action": "answered", "detail": "No evidence tools used."}),)
        if intent == "navigation":
            return (("activity", {"action": "focused", "detail": "Existing graph only."}),)
        nodes = cast(list[dict[str, object]], scene["nodes"])
        evidence = cast(list[dict[str, object]], scene["evidence"])
        brief = cast(dict[str, object] | None, scene.get("brief"))
        claim_count = len(cast(list[object], brief.get("claims", []))) if brief else 0
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
            ("activity", {"action": "claim_supported", "count": claim_count}),
            ("graph_delta", {"nodes": nodes, "edges": scene["edges"]}),
        )


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
