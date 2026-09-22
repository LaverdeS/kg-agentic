"""Bounded, in-memory conversation orchestration for the optional explorer."""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph


class ConversationState(TypedDict, total=False):
    question: str
    query: str
    mode: Literal["recorded", "live"]
    selected_node_ids: list[str]
    as_of: str | None
    scene: dict[str, object]
    history: Annotated[list[dict[str, str]], operator.add]


@dataclass(frozen=True)
class ConversationRequest:
    thread_id: str
    question: str
    mode: Literal["recorded", "live"]
    selected_node_ids: tuple[str, ...] = ()
    as_of: str | None = None


@dataclass(frozen=True)
class ConversationRun:
    events: tuple[tuple[str, dict[str, object]], ...]
    scene: dict[str, object]


SceneLoader = Callable[[str, Literal["recorded", "live"], str | None], dict[str, object]]


class ConversationRunner:
    """Retain only one local browser thread's public conversation context."""

    def __init__(self, load_scene: SceneLoader) -> None:
        self._load_scene = load_scene
        self._memory = InMemorySaver()
        workflow = StateGraph(ConversationState)
        workflow.add_node("plan", self._plan)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("support", self._support)
        workflow.add_edge(START, "plan")
        workflow.add_edge("plan", "retrieve")
        workflow.add_edge("retrieve", "support")
        self._graph = workflow.compile(checkpointer=self._memory)

    def run(self, request: ConversationRequest) -> ConversationRun:
        question = request.question.strip()
        if not question:
            raise ValueError("question must be a non-empty string")
        if not request.thread_id.strip():
            raise ValueError("threadId must be a non-empty string")
        if request.mode == "recorded" and request.as_of is not None:
            raise ValueError("An asOf date requires a live investigation.")

        state = cast(
            ConversationState,
            self._graph.invoke(
                {
                    "question": question,
                    "mode": request.mode,
                    "selected_node_ids": list(request.selected_node_ids),
                    "as_of": request.as_of,
                },
                {"configurable": {"thread_id": request.thread_id}},
            ),
        )
        scene = dict(cast(dict[str, object], state.get("scene")))
        node_ids = {
            cast(str, node["id"])
            for node in cast(list[dict[str, object]], scene["nodes"])
        }
        unknown_selection = set(request.selected_node_ids) - node_ids
        if unknown_selection:
            raise ValueError(
                "Selected graph context must refer to an element in this investigation."
            )

        scene["question"] = question
        scene["conversation"] = {
            "threadId": request.thread_id,
            "selectedNodeIds": list(request.selected_node_ids),
            "messages": state.get("history", [])[-8:],
            "asOf": request.as_of,
        }
        return ConversationRun(events=self._events(scene, request), scene=scene)

    def reset(self, thread_id: str) -> None:
        if not thread_id.strip():
            raise ValueError("threadId must be a non-empty string")
        self._memory.delete_thread(thread_id)

    def _plan(self, state: ConversationState) -> ConversationState:
        question = cast(str, state.get("question"))
        previous_questions = [
            message["content"]
            for message in state.get("history", [])
            if message["role"] == "user"
        ]
        context: list[str] = []
        if previous_questions:
            context.append(
                f"Earlier conversation question (not evidence): {previous_questions[-1]}"
            )
        if state.get("selected_node_ids"):
            selected = ", ".join(cast(list[str], state.get("selected_node_ids")))
            context.append(f"Selected graph context (not evidence): {selected}")
        query = "\n".join([*context, f"Current question: {question}"])
        return {"query": query, "history": [{"role": "user", "content": question}]}

    def _retrieve(self, state: ConversationState) -> ConversationState:
        return {
            "scene": self._load_scene(
                cast(str, state.get("query")),
                cast(Literal["recorded", "live"], state.get("mode")),
                state.get("as_of"),
            )
        }

    def _support(self, state: ConversationState) -> ConversationState:
        scene = cast(dict[str, object], state.get("scene"))
        brief = cast(dict[str, object] | None, scene.get("brief"))
        if state.get("mode") == "recorded":
            summary = (
                "Recorded walkthrough: this replays a fixed cited brief. Inspect the selected "
                "source evidence rather than treating it as a newly generated answer."
            )
        elif brief is None:
            summary = "The investigation abstained; inspect the recorded gaps before continuing."
        else:
            recommendation = cast(dict[str, object], brief["recommendation"])
            summary = cast(str, recommendation["text"])
        return {"history": [{"role": "assistant", "content": summary}]}

    @staticmethod
    def _events(
        scene: dict[str, object], request: ConversationRequest
    ) -> tuple[tuple[str, dict[str, object]], ...]:
        nodes = cast(list[dict[str, object]], scene["nodes"])
        evidence = cast(list[dict[str, object]], scene["evidence"])
        brief = cast(dict[str, object] | None, scene.get("brief"))
        claim_count = len(cast(list[object], brief.get("claims", []))) if brief else 0
        return (
            (
                "activity",
                {"action": "retrieved_path", "count": len(cast(list[object], scene["edges"]))},
            ),
            ("activity", {"action": "evidence_found", "count": len(evidence)}),
            ("activity", {"action": "claim_supported", "count": claim_count}),
            ("graph_delta", {"nodes": nodes, "edges": scene["edges"]}),
        )
