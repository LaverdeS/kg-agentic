"""OpenAI adapter for natural conversation and intentional evidence-tool routing."""

from __future__ import annotations

import json
import ssl
from typing import Literal

import httpx
import truststore
from openai import OpenAI
from pydantic import BaseModel

from kg_agentic.application.conversation import (
    ConversationDecision,
    ConversationModelRequest,
)
from kg_agentic.infrastructure.runtime import Settings

CONVERSATION_INSTRUCTIONS = """You are Mira, the research partner in Evidence Workbench.
Help a newcomer understand connected public research and decide what to check next. Answer in
plain language, explain unfamiliar terms, and connect a finding to why it matters and its limit.
Be warm, direct, and concise. Never assume the user knows the dataset or your tools.

Choose exactly one action:
- respond: greeting, definition, general explanation, help, or recap needing no live facts.
- inspect: current corpus counts, source categories, or what is in the visible research map.
- navigate: focus an element already visible; name it in navigation_target.
- investigate: source-backed findings, comparisons, partner paths, historical evidence, or an
  applied recommendation. Put a self-contained question in investigation_question.

An applied question about what to test, compare, or choose for a named approach needs investigate,
even if generic advice is possible. Use inspect for workspace statistics. Never give current corpus
facts or counts from memory. If retrieval_allowed is false, use no tools.

Only investigation can support cited research claims. A selected node is context, not proof.
Participation is not proven capability; objectives are not achieved results; metadata is not full
technical text; a missing public record is not proof of absence. Do not imply exhaustive coverage.
State uncertainty and the next validation step when evidence is thin.

For respond and navigate, put the complete answer in message. For inspect and investigate, use a
short transition. Keep message under 90 words. Do not reveal private reasoning or routing details.
Examples: "How many sources?" -> inspect; "What should this plant validate?" -> investigate."""

INSPECTION_INSTRUCTIONS = """You are Mira, the research partner in Evidence Workbench.
Answer the user's workspace question using only the supplied tool_result. Give a clear, concise
sentence or two in plain language. Distinguish source versions from unique documents and the
visible research map from the whole indexed corpus. An empty map means this conversation has not
built a research map yet. Do not infer unseen graph contents, capabilities, or source claims.
Do not reveal the tool schema or private reasoning."""


class _ConversationOutput(BaseModel):
    action: Literal["respond", "investigate", "navigate", "inspect"]
    message: str
    investigation_question: str | None = None
    navigation_target: str | None = None


class _InspectionAnswer(BaseModel):
    message: str


def generate_conversation_decision(
    settings: Settings,
    request: ConversationModelRequest,
) -> ConversationDecision:
    context = {
        "question": request.question,
        "recent_conversation": list(request.history[-6:]),
        "selected_graph_context": list(request.selected_node_ids),
        "historical_cutoff": request.as_of,
        "retrieval_allowed": request.retrieval_allowed,
        "tool_result": request.tool_result,
    }
    ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with (
        httpx.Client(verify=ssl_context) as http_client,
        OpenAI(api_key=settings.openai_api_key, http_client=http_client) as client,
    ):
        if request.tool_result is not None:
            inspection_response = client.responses.parse(
                model=settings.small_model,
                instructions=INSPECTION_INSTRUCTIONS,
                input=json.dumps(context, ensure_ascii=False),
                text_format=_InspectionAnswer,
                max_output_tokens=min(settings.model_max_output_tokens, 1600),
                reasoning={"effort": "minimal"},
                text={"verbosity": "low"},
                store=False,
            )
            answer = inspection_response.output_parsed
            if answer is None or not answer.message.strip():
                raise RuntimeError("The workspace inspection returned no answer")
            return ConversationDecision(action="respond", message=answer.message.strip())
        response = client.responses.parse(
            model=settings.small_model,
            instructions=CONVERSATION_INSTRUCTIONS,
            input=json.dumps(context, ensure_ascii=False),
            text_format=_ConversationOutput,
            max_output_tokens=min(settings.model_max_output_tokens, 1600),
            reasoning={"effort": "minimal"},
            text={"verbosity": "low"},
            store=False,
        )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The conversation model returned no decision")
    return ConversationDecision(
        action=parsed.action,
        message=parsed.message.strip(),
        investigation_question=(parsed.investigation_question or "").strip() or None,
        navigation_target=(parsed.navigation_target or "").strip() or None,
    )
