import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from kg_agentic.infrastructure.graphiti_adapter import GraphitiEvidenceMemory
from kg_agentic.knowledge.models import EvidenceItem, EvidenceKind


class RecordingGraphiti:
    def __init__(self) -> None:
        self.driver = None
        self.added = []
        self.searches = []

    async def add_episode(self, **kwargs):
        self.added.append(kwargs)

    async def search(self, query, *, group_ids, num_results):
        self.searches.append((query, group_ids, num_results))
        return [SimpleNamespace(episodes=["episode-1"])]


class RecordedEpisodeReader:
    def __init__(self, content: str) -> None:
        self.content = content

    async def load(self, episode_ids):
        assert episode_ids == ("episode-1",)
        return (self.content,)


class RecordedEvidenceCatalog:
    def __init__(self, items):
        self._items = items

    async def add(self, item):
        self._items = (*self._items, item)

    async def items(self, *, corpus_id):
        return tuple(item for item in self._items if item.corpus_id == corpus_id)


def evidence_item() -> EvidenceItem:
    return EvidenceItem(
        id="cordis-eurio:cement-v1:project-641185:sha256:abc",
        corpus_id="cordis-eurio:cement-v1",
        kind=EvidenceKind.SOURCE_CLAIM,
        text="CEMCAP reports objectives for retrofit capture comparisons.",
        source_url="https://cordis.europa.eu/project/id/641185",
        source_category="project_record",
        content_hash="sha256:abc",
        retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
        published_at=None,
        event_at=datetime(2015, 5, 1, tzinfo=UTC),
        passage="Identify technologies with retrofit potential.",
        canonical_entity_iris=("http://data.europa.eu/s66/resource/projects/example",),
        updated_at=None,
        ingested_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
        publication_year=2018,
        publication_precision="year",
    )


@pytest.mark.asyncio
async def test_graphiti_episode_round_trip_preserves_provenance() -> None:
    graphiti = RecordingGraphiti()
    item = evidence_item()
    adapter = GraphitiEvidenceMemory(
        graphiti,
        episode_reader=RecordedEpisodeReader(json.dumps(adapter_payload(item))),
    )

    await adapter.add(item)
    found = await adapter.search(query="retrofit capture", corpus_id=item.corpus_id, limit=4)

    added = graphiti.added[0]
    assert "uuid" not in added
    assert added["group_id"] == "cordis-eurio_u003a_cement-v1"
    assert added["source"].value == "json"
    assert added["reference_time"] == item.retrieved_at
    assert json.loads(added["episode_body"])["content_hash"] == "sha256:abc"
    assert graphiti.searches == [
        ("retrofit capture", ["cordis-eurio_u003a_cement-v1"], 4)
    ]
    assert found == (item,)


@pytest.mark.asyncio
async def test_graphiti_does_not_admit_year_precision_evidence_until_after_that_year() -> None:
    graphiti = RecordingGraphiti()
    item = evidence_item()
    adapter = GraphitiEvidenceMemory(
        graphiti,
        episode_reader=RecordedEpisodeReader(json.dumps(adapter_payload(item))),
        historical_catalog=RecordedEvidenceCatalog((item,)),
    )

    during_year = await adapter.search(
        query="retrofit capture",
        corpus_id=item.corpus_id,
        limit=4,
        as_of=datetime(2018, 12, 31, tzinfo=UTC),
    )
    after_year = await adapter.search(
        query="retrofit capture",
        corpus_id=item.corpus_id,
        limit=4,
        as_of=datetime(2019, 1, 1, tzinfo=UTC),
    )

    assert during_year == ()
    assert after_year == (item,)
    assert graphiti.searches == []


def adapter_payload(item: EvidenceItem) -> dict[str, object]:
    assert item.event_at is not None
    assert item.ingested_at is not None
    return {
        "id": item.id,
        "corpus_id": item.corpus_id,
        "kind": item.kind.value,
        "text": item.text,
        "source_url": item.source_url,
        "source_category": item.source_category,
        "content_hash": item.content_hash,
        "retrieved_at": item.retrieved_at.isoformat(),
        "published_at": None,
        "event_at": item.event_at.isoformat(),
        "passage": item.passage,
        "canonical_entity_iris": list(item.canonical_entity_iris),
        "updated_at": None,
        "ingested_at": item.ingested_at.isoformat(),
        "publication_year": item.publication_year,
        "publication_precision": item.publication_precision,
    }
