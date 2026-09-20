import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from kg_agentic.knowledge.models import EvidenceItem, SourceDocument


class EpisodeSink(Protocol):
    async def add(self, item: EvidenceItem) -> None: ...


class VersionIndex(Protocol):
    async def contains(self, version_id: str) -> bool: ...

    async def mark_ingested(self, version_id: str) -> None: ...


class SourceArchive(Protocol):
    async def save(
        self, *, document: SourceDocument, version_id: str, raw_bytes: bytes
    ) -> None: ...


class InMemoryVersionIndex:
    def __init__(self) -> None:
        self._versions: set[str] = set()

    async def contains(self, version_id: str) -> bool:
        return version_id in self._versions

    async def mark_ingested(self, version_id: str) -> None:
        self._versions.add(version_id)


class JsonVersionIndex:
    """Small durable index for source versions already accepted by the episode sink."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def contains(self, version_id: str) -> bool:
        return version_id in self._read()

    async def mark_ingested(self, version_id: str) -> None:
        versions = self._read()
        versions.add(version_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(sorted(versions), indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self._path)

    def _read(self) -> set[str]:
        if not self._path.exists():
            return set()
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise ValueError(f"Invalid version index: {self._path}")
        return set(payload)


class FileSourceArchive:
    """Store immutable source bytes under a path derived from the version identity."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    async def save(self, *, document: SourceDocument, version_id: str, raw_bytes: bytes) -> None:
        del document
        self._directory.mkdir(parents=True, exist_ok=True)
        safe_name = hashlib.sha256(version_id.encode("utf-8")).hexdigest()
        path = self._directory / f"{safe_name}.json"
        if path.exists():
            if path.read_bytes() != raw_bytes:
                raise ValueError(f"Archive collision for source version {version_id}")
            return
        path.write_bytes(raw_bytes)


@dataclass(frozen=True, slots=True)
class IngestionReport:
    received: int
    ingested: int
    skipped_unchanged: int
    version_ids: tuple[str, ...]


class IngestionPipeline:
    """Archive immutable source versions and add unseen evidence episodes."""

    def __init__(
        self,
        *,
        episode_sink: EpisodeSink,
        version_index: VersionIndex,
        archive: SourceArchive,
    ) -> None:
        self._episode_sink = episode_sink
        self._version_index = version_index
        self._archive = archive

    async def ingest(self, documents: tuple[SourceDocument, ...]) -> IngestionReport:
        ingested = 0
        skipped = 0
        version_ids: list[str] = []

        for document in documents:
            raw_bytes = document.raw_payload or _serialize_source(document)
            content_hash = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
            version_id = (
                f"{document.dataset_id}:{document.corpus_id}:{document.source_id}:{content_hash}"
            )
            version_ids.append(version_id)
            if await self._version_index.contains(version_id):
                skipped += 1
                continue

            item = EvidenceItem(
                id=version_id,
                corpus_id=f"{document.dataset_id}:{document.corpus_id}",
                kind=document.kind,
                text=document.text,
                source_url=document.source_url,
                source_category=document.source_category,
                content_hash=content_hash,
                retrieved_at=document.retrieved_at,
                published_at=document.publication_at,
                event_at=document.event_at,
                passage=document.passage,
                canonical_entity_iris=document.canonical_entity_iris,
                updated_at=document.update_at,
                ingested_at=datetime.now(UTC),
                publication_year=document.publication_year,
                publication_precision=document.publication_precision,
            )
            await self._archive.save(
                document=document,
                version_id=version_id,
                raw_bytes=raw_bytes,
            )
            await self._episode_sink.add(item)
            await self._version_index.mark_ingested(version_id)
            ingested += 1

        return IngestionReport(
            received=len(documents),
            ingested=ingested,
            skipped_unchanged=skipped,
            version_ids=tuple(version_ids),
        )


def _serialize_source(document: SourceDocument) -> bytes:
    payload = asdict(document)
    payload.pop("raw_payload", None)
    return json.dumps(payload, default=_json_default, sort_keys=True).encode("utf-8")


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")
