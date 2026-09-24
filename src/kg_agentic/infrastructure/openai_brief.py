import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kg_agentic.knowledge.models import (
    DraftBrief,
    DraftClaim,
    EvidenceItem,
    InvestigationPlan,
    StructuralPath,
)


class _ClaimOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=120)
    evidence_ids: list[str] = Field(min_length=1, max_length=1)


class _BriefOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: _ClaimOutput
    recommendation: _ClaimOutput
    alternatives: list[_ClaimOutput] = Field(min_length=1, max_length=1)
    uncertainty: _ClaimOutput
    next_action: _ClaimOutput
    claims: list[_ClaimOutput] = Field(min_length=1, max_length=1)


class OpenAIBriefGenerator:
    """Generate a structured draft; support enforcement remains in the application module."""

    def __init__(self, client: Any, *, model: str, max_output_tokens: int) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self.last_usage: dict[str, int] = {}

    async def generate(
        self,
        *,
        question: str,
        plan: InvestigationPlan,
        paths: tuple[StructuralPath, ...],
        evidence: tuple[EvidenceItem, ...],
    ) -> DraftBrief:
        context = {
            "question": question,
            "bounded_plan": list(plan.actions),
            "structural_paths": [_path_payload(path) for path in paths],
            "evidence": [_evidence_payload(item) for item in evidence],
        }
        response = await self._client.responses.parse(
            model=self._model,
            instructions=(
                "Write a concise consulting recommendation for a feasibility-study decision. "
                "Use only the supplied structural paths and evidence. Treat structured facts, "
                "source-reported claims, unverified model extractions, and hypotheses according "
                "to their labels. Objectives do not prove achievement; participation does not "
                "prove capability or authorship; missing public data does not prove absence. "
                "Every brief field is a support-bearing statement and must list one or more exact "
                "supplied evidence IDs. Do not expose private reasoning; return only the requested "
                "brief fields. Write complete, plain-language sentences for a reader unfamiliar "
                "with the dataset or technical shorthand; expand acronyms when space permits. "
                "Keep every text field below 120 characters. "
                "Cite exactly one evidence ID per field; give exactly one alternative and at most "
                "one supporting claim. Do not repeat context or citations in prose."
            ),
            input=json.dumps(context, ensure_ascii=False),
            text_format=_BriefOutput,
            max_output_tokens=self._max_output_tokens,
            reasoning={"effort": "minimal"},
            text={"verbosity": "low"},
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("The model returned no structured recommendation brief")
        usage = getattr(response, "usage", None)
        self.last_usage = {
            name: int(getattr(usage, name, 0) or 0)
            for name in ("input_tokens", "output_tokens", "total_tokens")
        }
        return DraftBrief(
            decision=_draft_claim(parsed.decision),
            recommendation=_draft_claim(parsed.recommendation),
            alternatives=tuple(_draft_claim(item) for item in parsed.alternatives),
            uncertainty=_draft_claim(parsed.uncertainty),
            next_action=_draft_claim(parsed.next_action),
            claims=tuple(
                DraftClaim(text=claim.text, evidence_ids=tuple(claim.evidence_ids))
                for claim in parsed.claims
            ),
    )


def _draft_claim(value: _ClaimOutput) -> DraftClaim:
    return DraftClaim(text=value.text, evidence_ids=tuple(value.evidence_ids))


def _path_payload(path: StructuralPath) -> list[dict[str, object]]:
    return [
        {
            "subject": edge.subject,
            "predicate": edge.predicate,
            "object": edge.object,
            "source_url": edge.source_url,
            "attributes": dict(edge.attributes),
        }
        for edge in path.relationships
    ]


def _evidence_payload(item: EvidenceItem) -> dict[str, object]:
    return {
        "id": item.id,
        "kind": item.kind.value,
        "text": item.text,
        "passage": item.passage,
        "source_url": item.source_url,
        "source_category": item.source_category,
        "publication_at": item.published_at.isoformat() if item.published_at else None,
        "publication_year": item.publication_year,
        "publication_precision": item.publication_precision,
        "event_at": item.event_at.isoformat() if item.event_at else None,
        "canonical_entity_iris": list(item.canonical_entity_iris),
    }
