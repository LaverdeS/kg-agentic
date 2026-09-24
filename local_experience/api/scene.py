"""Vendor-neutral scene projection for the local explorer.

This module lives outside the core package intentionally.  It consumes the public
investigation models and exposes plain JSON-shaped scene data to the browser.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import cast

from kg_agentic.application.cement import LIVE_SEED_PROJECTS
from kg_agentic.knowledge.models import (
    EvidenceItem,
    InvestigationResult,
    Relationship,
    StructuralPath,
)


@dataclass(frozen=True, slots=True)
class SceneNode:
    id: str
    label: str
    kind: str
    source_url: str | None
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class SceneEdge:
    id: str
    source: str
    target: str
    label: str
    source_url: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class InvestigationScene:
    question: str
    status: str
    mode: str
    nodes: tuple[SceneNode, ...]
    edges: tuple[SceneEdge, ...]
    evidence: tuple[dict[str, object], ...]
    brief: dict[str, object] | None
    trace: tuple[dict[str, object], ...]
    gaps: tuple[str, ...]


def project_scene(result: InvestigationResult, *, mode: str) -> InvestigationScene:
    """Project only retrieved paths and evidence; never expose storage internals."""
    nodes, edges = project_graph(result.paths, result.evidence)
    return InvestigationScene(
        question=result.plan.question,
        status=result.status,
        mode=mode,
        nodes=nodes,
        edges=edges,
        evidence=tuple(_evidence_payload(item) for item in result.evidence),
        brief=_brief_payload(result),
        trace=tuple(asdict(step) for step in result.trace),
        gaps=result.gaps,
    )


def project_graph(
    paths: tuple[StructuralPath, ...], evidence: tuple[EvidenceItem, ...]
) -> tuple[tuple[SceneNode, ...], tuple[SceneEdge, ...]]:
    """Translate a partial or completed retrieval into the same neutral graph contract."""
    nodes: dict[str, SceneNode] = {}
    edges: dict[str, SceneEdge] = {}

    for path in paths:
        for relationship in path.relationships:
            _add_relationship(nodes, edges, relationship)

    for item in evidence:
        evidence_id = f"evidence:{item.id}"
        nodes[evidence_id] = SceneNode(
            id=evidence_id,
            label=_evidence_label(item),
            kind="evidence",
            source_url=item.source_url,
            metadata={
                "evidenceId": item.id,
                "sourceCategory": item.source_category,
                "strength": item.kind.value,
                "passage": item.passage,
                "contentHash": item.content_hash,
                "corpusId": item.corpus_id,
                "retrievedAt": _timestamp(item.retrieved_at),
                "publishedAt": _timestamp(item.published_at),
                "eventAt": _timestamp(item.event_at),
                "updatedAt": _timestamp(item.updated_at),
                "ingestedAt": _timestamp(item.ingested_at),
                "canonicalEntityIds": item.canonical_entity_iris,
                "publicationYear": item.publication_year,
                "publicationPrecision": item.publication_precision,
                "text": item.text,
            },
        )
        for entity_id in item.canonical_entity_iris:
            if entity_id not in nodes:
                nodes[entity_id] = _entity_node(entity_id)
            edge_id = f"{evidence_id}|supports|{entity_id}"
            edges[edge_id] = SceneEdge(
                id=edge_id,
                source=evidence_id,
                target=entity_id,
                label="supports",
                source_url=item.source_url,
                metadata={"provenance": "retrieved evidence"},
            )

    return tuple(nodes.values()), tuple(edges.values())


def scene_payload(scene: InvestigationScene) -> dict[str, object]:
    return cast(dict[str, object], _json_value(asdict(scene)))


def _add_relationship(
    nodes: dict[str, SceneNode], edges: dict[str, SceneEdge], relationship: Relationship
) -> None:
    nodes.setdefault(relationship.subject, _entity_node(relationship.subject))
    nodes.setdefault(relationship.object, _entity_node(relationship.object))
    role_label = dict(relationship.attributes).get("roleLabel")
    if role_label and _resource_type(relationship.subject) == "role":
        nodes[relationship.subject] = SceneNode(
            id=relationship.subject,
            label=f"{role_label.replace('_', ' ')} role",
            kind="role",
            source_url=relationship.source_url,
            metadata={
                "identifier": relationship.subject,
                "resourceType": "role",
                "roleLabel": role_label,
            },
        )
    edge_id = "|".join((relationship.subject, relationship.predicate, relationship.object))
    edges[edge_id] = SceneEdge(
        id=edge_id,
        source=relationship.subject,
        target=relationship.object,
        label=_short_name(relationship.predicate),
        source_url=relationship.source_url,
        metadata={"predicate": relationship.predicate, "attributes": dict(relationship.attributes)},
    )


def _entity_node(entity_id: str) -> SceneNode:
    resource_type = _resource_type(entity_id)
    return SceneNode(
        id=entity_id,
        label=_entity_label(entity_id),
        kind=resource_type,
        source_url=None,
        metadata={"identifier": entity_id, "resourceType": resource_type},
    )


def _resource_type(entity_id: str) -> str:
    for kind in ("projects", "organisations", "organisationroles", "results"):
        if f"/{kind}/" in entity_id:
            return {
                "projects": "project",
                "organisations": "organization",
                "organisationroles": "role",
                "results": "output",
            }[kind]
    return "entity"


def _entity_label(entity_id: str) -> str:
    project = next((project for project in LIVE_SEED_PROJECTS if project.iri == entity_id), None)
    if project is not None:
        return f"{project.acronym} · {project.grant_id}"
    known_entities = {
        "5ddbaa23-06d6-39f8-8b9f-9fd78d53f149": "LEAP",
        "671b76de-97f6-3c7e-8f4a-18cd5c5a24ce": "POLIMI",
        "2cc39403-e975-327f-8657-8df803af027d": "CEMCAP result metadata",
        "461c02da-5450-3ad1-ba61-10d85f5c4583": "LEILAC2 result metadata",
        "9c2afdde-8a12-365e-b1e3-e2d80d3e115c": "CEMCAP framework metadata",
        "afaf42f5-15c7-3c14-ba5b-012eb4c8b2ac": "CEMCAP ammonia publication metadata",
        "2d34f8d6-c3ec-3593-8bb1-12e4a264a6a9": "HERCCULES result metadata",
    }
    short_name = _short_name(entity_id)
    if short_name in known_entities:
        return known_entities[short_name]
    resource_type = _resource_type(entity_id)
    if len(short_name) == 36 and short_name.count("-") == 4:
        prefix = {
            "organization": "Organisation",
            "output": "Research output",
            "project": "Research project",
            "role": "Participant role",
        }.get(resource_type, "Evidence entity")
        return f"{prefix} · {short_name[:8]}"
    return short_name


def _evidence_label(item: EvidenceItem) -> str:
    project = (
        _entity_label(item.canonical_entity_iris[0]) if item.canonical_entity_iris else "Evidence"
    )
    return f"{project} · {item.source_category.replace('_', ' ')}"


def _evidence_payload(item: EvidenceItem) -> dict[str, object]:
    return cast(
        dict[str, object],
        _json_value(
            {
                "id": item.id,
                "nodeId": f"evidence:{item.id}",
                "kind": item.kind,
                "text": item.text,
                "passage": item.passage,
                "sourceUrl": item.source_url,
            "sourceCategory": item.source_category,
            "contentHash": item.content_hash,
            "corpusId": item.corpus_id,
            "retrievedAt": item.retrieved_at,
            "publishedAt": item.published_at,
            "eventAt": item.event_at,
            "updatedAt": item.updated_at,
            "ingestedAt": item.ingested_at,
                "publicationYear": item.publication_year,
                "publicationPrecision": item.publication_precision,
                "canonicalEntityIds": item.canonical_entity_iris,
            }
        ),
    )


def _brief_payload(result: InvestigationResult) -> dict[str, object] | None:
    if result.brief is None:
        return None
    return cast(dict[str, object], _json_value(asdict(result.brief)))


def _short_name(value: str) -> str:
    return value.rsplit("/", maxsplit=1)[-1].rsplit("#", maxsplit=1)[-1]


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value
