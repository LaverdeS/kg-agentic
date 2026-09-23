"""Live, tool-oriented conversation orchestration for the optional explorer.

The explorer intentionally keeps no graph snapshot. Browser message history is
checkpointed locally, while each investigation invokes the core composition
again and projects only that run's returned paths and evidence.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict, cast

from langgraph.graph import START, StateGraph

SYSTEM_PROMPT = """You help turn European research relationships and dated public
sources into decisions people can inspect. Use a live tool before answering. Keep
structural relationships separate from source claims, make uncertainty explicit,
and never turn project participation, objectives, or missing data into proof."""

TEST_TASKS = (
    "Compare CEMCAP and LEILAC2 for a retrofit decision; name the unsafe assumptions.",
    "Find evidence that would support or rule out an oxyfuel retrofit pathway.",
    "Identify partners worth validating for complementary capture work and the evidence needed.",
    "Surface the decision-critical gap in a cement retrofit shortlist and a next validation step.",
    "Ask what the currently retrieved public sources establish versus what remains unverified.",
    "Run the same question with a strict historical date and inspect the abstention or gaps.",
)

Intent = Literal["investigation", "help", "conversation"]
SceneLoader = Callable[[str, str | None], dict[str, object]]
RuntimeChecker = Callable[[], dict[str, object]]
TaskRecommender = Callable[[], tuple[str, ...]]


class ConversationState(TypedDict, total=False):
    question: str
    query: str
    selected_node_ids: list[str]
    as_of: str | None
    intent: Intent
    scene: dict[str, object]
    runtime: dict[str, object]
    tasks: tuple[str, ...]
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
    """A LangGraph agent that acts through three explicitly bound live tools.

    The policy is intentionally bounded rather than an unconstrained second LLM:
    the existing core agent is the authority for retrieval and the supported
    recommendation. This wrapper chooses a tool, preserves chat text, and never
    reuses a former scene as evidence.
    """

    tool_names = ("check_live_services", "recommend_test_tasks", "investigate_live_graph")

    def __init__(
        self,
        investigate_live_graph: SceneLoader,
        check_live_services: RuntimeChecker,
        recommend_test_tasks: TaskRecommender,
    ) -> None:
        self._investigate_live_graph = investigate_live_graph
        self._check_live_services = check_live_services
        self._recommend_test_tasks = recommend_test_tasks
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
        scene = dict(cast(dict[str, object], state.get("scene")))
        scene["question"] = question
        scene["conversation"] = {
            "threadId": request.thread_id,
            "selectedNodeIds": list(request.selected_node_ids),
            "messages": state.get("history", [])[-8:],
            "asOf": request.as_of,
            "intent": intent,
        }
        self._history_by_thread[request.thread_id] = cast(
            list[dict[str, str]], state.get("history", [])[-8:]
        )
        return ConversationRun(events=self._events(scene, intent), scene=scene)

    @staticmethod
    def public_activity(request: ConversationRequest) -> dict[str, str]:
        intent = _intent(request.question)
        return {
            "action": "planned" if intent == "investigation" else "checked_live_services",
            "detail": (
                "Starting a new live graph investigation. No previous result will be reused."
                if intent == "investigation"
                else "Checking the live workspace before replying; no graph result is seeded."
            ),
        }

    def reset(self, thread_id: str) -> None:
        if not thread_id.strip():
            raise ValueError("threadId must be a non-empty string")
        self._history_by_thread.pop(thread_id, None)

    def _reason(self, state: ConversationState) -> ConversationState:
        question = cast(str, state.get("question"))
        intent = _intent(question)
        if intent != "investigation":
            return {"intent": intent, "history": [{"role": "user", "content": question}]}

        previous_questions = [
            message["content"]
            for message in state.get("history", [])
            if message["role"] == "user"
        ]
        context = [SYSTEM_PROMPT]
        if previous_questions:
            context.append(f"Earlier question for context only: {previous_questions[-1]}")
        if state.get("selected_node_ids"):
            selected = ", ".join(cast(list[str], state.get("selected_node_ids")))
            context.append(f"Selected UI context, not evidence: {selected}")
        context.append(f"Current user question: {question}")
        return {
            "intent": intent,
            "query": "\n\n".join(context),
            "history": [{"role": "user", "content": question}],
        }

    def _act(self, state: ConversationState) -> ConversationState:
        intent = cast(Intent, state.get("intent"))
        if intent == "investigation":
            return {
                "scene": self._investigate_live_graph(
                    cast(str, state.get("query")), state.get("as_of")
                )
            }
        runtime = self._check_live_services()
        tasks = self._recommend_test_tasks()
        return {"runtime": runtime, "tasks": tasks, "scene": _empty_scene()}

    def _respond(self, state: ConversationState) -> ConversationState:
        intent = cast(Intent, state.get("intent"))
        if intent == "investigation":
            scene = cast(dict[str, object], state.get("scene"))
            brief = cast(dict[str, object] | None, scene.get("brief"))
            if brief is None:
                response = (
                    "I checked the live graph, but it could not support a full recommendation. "
                    "The gaps below show what to validate next."
                )
            else:
                recommendation = cast(dict[str, object], brief["recommendation"])
                response = cast(str, recommendation["text"])
            return {"history": [{"role": "assistant", "content": response}]}

        runtime = cast(dict[str, object], state.get("runtime"))
        tasks = cast(tuple[str, ...], state.get("tasks"))
        if intent == "help":
            response = (
                "I use live tools, not a recorded example. Ask a decision question and I will "
                "run the graph, then show only the returned paths, sources, and supported brief. "
                f"Live service check: {runtime['summary']}. Try one of these: "
                + " ".join(f"{index + 1}. {task}" for index, task in enumerate(tasks[:5]))
            )
        else:
            response = (
                "I’m ready. I checked the live workspace and will not reuse an old graph result. "
                f"{runtime['summary']} Ask a decision question, or try: {tasks[0]}"
            )
        return {"history": [{"role": "assistant", "content": response}]}

    @staticmethod
    def _events(
        scene: dict[str, object], intent: Intent
    ) -> tuple[tuple[str, dict[str, object]], ...]:
        if intent != "investigation":
            return (("activity", {"action": "recommended_tasks", "count": 6}),)
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


def _intent(question: str) -> Intent:
    normalized = " ".join(question.lower().split())
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
        "who are you",
        "how do i use this",
    )
    task_markers = (
        "test task",
        "test tasks",
        "examples",
        "example",
        "what can i try",
        "what should i try",
        "suggest a task",
        "suggest tasks",
    )
    if any(marker in normalized for marker in (*help_markers, *task_markers)):
        return "help"
    casual_turns = {"how are you", "how are things", "great", "nice", "sounds good"}
    casual_starts = ("hello", "hey", "good morning", "good afternoon", "good evening", "thanks")
    if normalized.strip(" !?.") in casual_turns or normalized.startswith(casual_starts):
        return "conversation"
    return "investigation"
