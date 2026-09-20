from datetime import UTC, datetime

import pytest

from kg_agentic.knowledge.ingestion import (
    FileSourceArchive,
    IngestionPipeline,
    InMemoryVersionIndex,
    JsonVersionIndex,
)
from kg_agentic.knowledge.models import EvidenceKind, SourceDocument


class RecordingEpisodeSink:
    def __init__(self) -> None:
        self.items = []

    async def add(self, item):
        self.items.append(item)


class RecordingArchive:
    def __init__(self) -> None:
        self.versions = []

    async def save(self, *, document, version_id, raw_bytes):
        self.versions.append((document.source_id, version_id, raw_bytes))


@pytest.mark.asyncio
async def test_reingesting_same_source_version_is_idempotent() -> None:
    sink = RecordingEpisodeSink()
    archive = RecordingArchive()
    pipeline = IngestionPipeline(
        episode_sink=sink,
        version_index=InMemoryVersionIndex(),
        archive=archive,
    )
    document = SourceDocument(
        dataset_id="cordis-eurio",
        corpus_id="cement-v1",
        source_id="cordis-project-641185",
        source_url="https://cordis.europa.eu/project/id/641185",
        source_category="project_record",
        text="CEMCAP compared post-combustion capture technologies for cement plants.",
        passage="CEMCAP compared post-combustion capture technologies for cement plants.",
        kind=EvidenceKind.SOURCE_CLAIM,
        canonical_entity_iris=(
            "http://data.europa.eu/s66/resource/projects/91b4e591-b2dd-357a-9556-45feba981888",
        ),
        publication_at=None,
        update_at=None,
        event_at=None,
        retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
    )

    first = await pipeline.ingest((document,))
    second = await pipeline.ingest((document,))

    assert first.ingested == 1
    assert second.skipped_unchanged == 1
    assert len(sink.items) == 1
    assert len(archive.versions) == 1
    assert sink.items[0].id.startswith("cordis-eurio:cement-v1:cordis-project-641185:sha256:")
    assert sink.items[0].content_hash.startswith("sha256:")


@pytest.mark.asyncio
async def test_file_version_index_survives_reopening(tmp_path) -> None:
    document = SourceDocument(
        dataset_id="synthetic-infrastructure",
        corpus_id="bridge-v1",
        source_id="inspection/bridge:42",
        source_url="https://example.test/inspections/bridge-42",
        source_category="inspection",
        text="Bearing replacement was recommended.",
        passage="Bearing replacement was recommended.",
        kind=EvidenceKind.SOURCE_CLAIM,
        canonical_entity_iris=("asset:bridge-42",),
        publication_at=datetime(2025, 1, 2, tzinfo=UTC),
        update_at=None,
        event_at=datetime(2024, 12, 12, tzinfo=UTC),
        retrieved_at=datetime(2026, 9, 20, tzinfo=UTC),
    )
    sink = RecordingEpisodeSink()
    index_path = tmp_path / "versions.json"
    archive = FileSourceArchive(tmp_path / "raw")

    first = IngestionPipeline(
        episode_sink=sink,
        version_index=JsonVersionIndex(index_path),
        archive=archive,
    )
    second = IngestionPipeline(
        episode_sink=sink,
        version_index=JsonVersionIndex(index_path),
        archive=archive,
    )

    await first.ingest((document,))
    report = await second.ingest((document,))

    assert report.skipped_unchanged == 1
    assert len(list((tmp_path / "raw").glob("*.json"))) == 1
