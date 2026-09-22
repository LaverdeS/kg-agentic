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
    intent: Literal["investigation", "help"]
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
SceneSnapshot = Callable[[], dict[str, object]]


class ConversationRunner:
    """Retain only one local browser thread's public conversation context."""

    def __init__(self, load_scene: SceneLoader, snapshot_scene: SceneSnapshot) -> None:
        self._load_scene = load_scene
        self._snapshot_scene = snapshot_scene
        self._memory = InMemorySaver()
        workflow = StateGraph(ConversationState)
        workflow.add_node("plan", self._plan)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("support", self._support)
        workflow.add_node("help", self._help)
        workflow.add_edge(START, "plan")
        workflow.add_conditional_edges(
            "plan",
            lambda state: cast(Literal["investigation", "help"], state["intent"]),
            {"investigation": "retrieve", "help": "help"},
        )
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
            "intent": state["intent"],
        }
        return ConversationRun(events=self._events(scene, request), scene=scene)

    @staticmethod
    def public_activity(request: ConversationRequest) -> dict[str, str]:
        if _intent(request.question) == "help":
            return {
                "action": "oriented",
                "detail": "Explaining the local explorer without starting retrieval.",
            }
        return {
            "action": "planned",
            "detail": (
                f"Using {len(request.selected_node_ids)} selected graph element(s) as navigation "
                "context."
                if request.selected_node_ids
                else "Starting a bounded investigation."
            ),
        }

    def reset(self, thread_id: str) -> None:
        if not thread_id.strip():
            raise ValueError("threadId must be a non-empty string")
        self._memory.delete_thread(thread_id)

    def _plan(self, state: ConversationState) -> ConversationState:
        question = cast(str, state.get("question"))
        intent = _intent(question)
        if intent == "help":
            return {
                "intent": intent,
                "history": [{"role": "user", "content": question}],
            }
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
        return {
            "intent": intent,
            "query": query,
            "history": [{"role": "user", "content": question}],
        }

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

    def _help(self, state: ConversationState) -> ConversationState:
        return {
            "scene": self._snapshot_scene(),
            "history": [
                {
                    "role": "assistant",
                    "content": (
                        "This is a local evidence explorer for a cement-retrofit decision. "
                        "The constellation links the retrieved EURIO organization-project-output "
                        "paths with source-qualified evidence; the rail keeps cited claims and "
                        "their provenance inspectable. Recorded mode replays a fixed current "
                        "snapshot. Live mode can call the configured EURIO, Neo4j, and model "
                        "services for a bounded investigation, but this help answer does not query "
                        "live services or change the graph. Select an element to focus its "
                        "neighborhood, or ask a consulting question when you want new retrieval."
                    ),
                }
            ],
        }

    @staticmethod
    def _events(
        scene: dict[str, object], request: ConversationRequest
    ) -> tuple[tuple[str, dict[str, object]], ...]:
        if scene["conversation"].get("intent") == "help":
            return ()
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


def _intent(question: str) -> Literal["investigation", "help"]:
    normalized = question.lower()
    help_markers = (
        "what is this",
        "what is the app",
        "what can you do",
        "what tools",
        "what data",
        "what sources",
        "are you connected",
        "help me",
        "how does this work",
    )
    return "help" if any(marker in normalized for marker in help_markers) else "investigation"
