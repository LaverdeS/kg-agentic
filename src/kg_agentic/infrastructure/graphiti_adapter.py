import json
from datetime import datetime
from typing import Any, Literal, Protocol

from graphiti_core.nodes import EpisodeType, EpisodicNode

from kg_agentic.knowledge.catalog import EvidenceCatalog
from kg_agentic.knowledge.models import EvidenceItem, EvidenceKind
from kg_agentic.knowledge.temporal import is_evidence_public_by


class EpisodeReader(Protocol):
    async def load(self, episode_ids: tuple[str, ...]) -> tuple[str, ...]: ...


class GraphitiEpisodeReader:
    def __init__(self, driver: Any) -> None:
        self._driver = driver

    async def load(self, episode_ids: tuple[str, ...]) -> tuple[str, ...]:
        if not episode_ids:
            return ()
        nodes = await EpisodicNode.get_by_uuids(self._driver, list(episode_ids))
        by_id = {node.uuid: node.content for node in nodes}
        return tuple(by_id[episode_id] for episode_id in episode_ids if episode_id in by_id)


class GraphitiEvidenceMemory:
    """Store and retrieve source-qualified evidence through Graphiti episodes."""

    def __init__(
        self,
        graphiti: Any,
        *,
        episode_reader: EpisodeReader | None = None,
        historical_catalog: EvidenceCatalog | None = None,
    ) -> None:
        self._graphiti = graphiti
        self._episode_reader = episode_reader or GraphitiEpisodeReader(graphiti.driver)
        self._historical_catalog = historical_catalog

    async def add(self, item: EvidenceItem) -> None:
        await self._graphiti.add_episode(
            name=item.id,
            episode_body=json.dumps(_to_payload(item), ensure_ascii=False, sort_keys=True),
            source_description=(
                f"{item.source_category} source version from {item.source_url}; "
                "objectives and reported claims are not independently verified achievements"
            ),
            reference_time=item.published_at or item.retrieved_at,
            source=EpisodeType.json,
            group_id=_graphiti_group_id(item.corpus_id),
            custom_extraction_instructions=(
                "Extract only claims present in the text field. Preserve uncertainty and do not "
                "infer publication dates, achievement, capability, or authorship from metadata."
            ),
        )

    async def search(
        self,
        *,
        query: str,
        corpus_id: str,
        limit: int,
        as_of: datetime | None = None,
    ) -> tuple[EvidenceItem, ...]:
        if as_of is not None:
            if self._historical_catalog is None:
                return ()
            candidates = await self._historical_catalog.items(corpus_id=corpus_id)
            eligible = (item for item in candidates if is_evidence_public_by(item, as_of))
            ranked = sorted(eligible, key=lambda item: _relevance(query, item), reverse=True)
            return tuple(ranked[:limit])
        edges = await self._graphiti.search(
            query,
            group_ids=[_graphiti_group_id(corpus_id)],
            num_results=limit,
        )
        episode_ids = tuple(
            dict.fromkeys(
                episode_id
                for edge in edges
                for episode_id in getattr(edge, "episodes", ())
                if isinstance(episode_id, str)
            )
        )
        contents = await self._episode_reader.load(episode_ids)
        found: list[EvidenceItem] = []
        seen: set[str] = set()
        for content in contents:
            item = _from_payload(json.loads(content))
            if (
                item.corpus_id != corpus_id
                or item.id in seen
                or (as_of is not None and not is_evidence_public_by(item, as_of))
            ):
                continue
            seen.add(item.id)
            found.append(item)
            if len(found) >= limit:
                break
        return tuple(found)


def _to_payload(item: EvidenceItem) -> dict[str, object]:
    return {
        "id": item.id,
        "corpus_id": item.corpus_id,
        "kind": item.kind.value,
        "text": item.text,
        "source_url": item.source_url,
        "source_category": item.source_category,
        "content_hash": item.content_hash,
        "retrieved_at": item.retrieved_at.isoformat(),
        "published_at": _iso(item.published_at),
        "event_at": _iso(item.event_at),
        "passage": item.passage,
        "canonical_entity_iris": list(item.canonical_entity_iris),
        "updated_at": _iso(item.updated_at),
        "ingested_at": _iso(item.ingested_at),
        "publication_year": item.publication_year,
        "publication_precision": item.publication_precision,
        "source_id": item.source_id,
        "supersedes_id": item.supersedes_id,
        "contradicts_ids": list(item.contradicts_ids),
    }


def _from_payload(payload: object) -> EvidenceItem:
    if not isinstance(payload, dict):
        raise ValueError("Graphiti evidence episode must contain a JSON object")
    try:
        canonical_iris = payload["canonical_entity_iris"]
        if not isinstance(canonical_iris, list) or not all(
            isinstance(value, str) for value in canonical_iris
        ):
            raise ValueError("canonical_entity_iris must be a list of strings")
        return EvidenceItem(
            id=str(payload["id"]),
            corpus_id=str(payload["corpus_id"]),
            kind=EvidenceKind(str(payload["kind"])),
            text=str(payload["text"]),
            source_url=str(payload["source_url"]),
            source_category=str(payload["source_category"]),
            content_hash=str(payload["content_hash"]),
            retrieved_at=_required_datetime(payload["retrieved_at"]),
            published_at=_optional_datetime(payload.get("published_at")),
            event_at=_optional_datetime(payload.get("event_at")),
            passage=_optional_string(payload.get("passage")),
            canonical_entity_iris=tuple(canonical_iris),
            updated_at=_optional_datetime(payload.get("updated_at")),
            ingested_at=_optional_datetime(payload.get("ingested_at")),
            publication_year=_optional_int(payload.get("publication_year")),
            publication_precision=_optional_year_precision(payload.get("publication_precision")),
            source_id=_optional_string(payload.get("source_id")),
            supersedes_id=_optional_string(payload.get("supersedes_id")),
            contradicts_ids=_optional_strings(payload.get("contradicts_ids")),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid Graphiti evidence episode") from error


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _required_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("datetime is required")
    return datetime.fromisoformat(value)


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _required_datetime(value)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("integer or null is required")
    return value


def _optional_strings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("list of strings or null is required")
    return tuple(value)


def _optional_year_precision(value: object) -> Literal["year"] | None:
    if value is None:
        return None
    if value != "year":
        raise ValueError("year precision or null is required")
    return "year"


def _graphiti_group_id(corpus_id: str) -> str:
    """Encode logical source-qualified IDs using Graphiti's restricted alphabet."""
    return "".join(
        character
        if character.isascii() and (character.isalnum() or character in "-_")
        else f"_u{ord(character):04x}_"
        for character in corpus_id
    )


def _relevance(query: str, item: EvidenceItem) -> int:
    terms = {term for term in query.lower().split() if len(term) > 2}
    document = f"{item.text} {item.passage or ''}".lower()
    return sum(term in document for term in terms)
