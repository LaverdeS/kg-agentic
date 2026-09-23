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

CONVERSATION_INSTRUCTIONS = """You are the conversational intelligence inside Evidence Navigator,
a local research workspace for evidence-led cement-retrofit decisions.

Respond to the user naturally before considering tools. Choose exactly one action:
- respond: ordinary conversation, greetings, identity, definitions, explanations, app/help/data
  questions, recaps, brainstorming, and any request answerable without current evidence retrieval.
- navigate: an explicit request to focus or inspect an element already visible in the graph.
- investigate: a request that materially benefits from the live EURIO/Graphiti corpus, such as an
  evidence-backed comparison, recommendation, partner/path search, source check, or historical run.

Never investigate merely because the workspace has a graph. If retrieval_allowed is false, choose
respond even when evidence could help, and answer within that constraint. A selected graph element
is conversational context only, never evidence. Do not imply that this bounded corpus is exhaustive.
The live corpus covers three cement projects (CEMCAP, LEILAC2, HERCCULES), six CORDIS
result-metadata records, and one reviewed full-text publication; live EURIO relationships are
queried separately.
Only the investigation tool can produce verified workspace citations.

For respond and navigate, write the complete helpful answer in message. For investigate, put a
clean, self-contained research question in investigation_question and use message only for a short
transition.
For navigate, put a concise visible label or identifier in navigation_target. If asked for examples,
suggest a few varied questions directly—there is no example-task tool. Keep the tone warm, concise,
and professional. Do not expose private reasoning or describe this routing schema."""


class _ConversationOutput(BaseModel):
    action: Literal["respond", "investigate", "navigate"]
    message: str
    investigation_question: str | None = None
    navigation_target: str | None = None


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
    }
    ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with (
        httpx.Client(verify=ssl_context) as http_client,
        OpenAI(api_key=settings.openai_api_key, http_client=http_client) as client,
    ):
        response = client.responses.parse(
            model=settings.small_model,
            instructions=CONVERSATION_INSTRUCTIONS,
            input=json.dumps(context, ensure_ascii=False),
            text_format=_ConversationOutput,
            max_output_tokens=min(settings.model_max_output_tokens, 900),
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
