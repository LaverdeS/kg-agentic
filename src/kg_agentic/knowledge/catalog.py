import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from kg_agentic.knowledge.models import EvidenceItem, EvidenceKind


class EvidenceCatalog(Protocol):
    async def add(self, item: EvidenceItem) -> None: ...

    async def items(self, *, corpus_id: str) -> tuple[EvidenceItem, ...]: ...


class JsonEvidenceCatalog:
    """Small durable, source-version catalog for historical retrieval without graph state."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def add(self, item: EvidenceItem) -> None:
        entries = self._read()
        if any(existing.id == item.id for existing in entries):
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entries.append(item)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(
            json.dumps([asdict(entry) for entry in entries], default=_json_default, indent=2)
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self._path)

    async def items(self, *, corpus_id: str) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self._read() if item.corpus_id == corpus_id)

    def _read(self) -> list[EvidenceItem]:
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Invalid evidence catalog: {self._path}")
        return [_item(entry) for entry in payload]


def _item(value: object) -> EvidenceItem:
    if not isinstance(value, dict):
        raise ValueError("Invalid evidence catalog entry")
    try:
        return EvidenceItem(
            id=str(value["id"]),
            corpus_id=str(value["corpus_id"]),
            kind=EvidenceKind(str(value["kind"])),
            text=str(value["text"]),
            source_url=str(value["source_url"]),
            source_category=str(value["source_category"]),
            content_hash=str(value["content_hash"]),
            retrieved_at=_date(value["retrieved_at"]),
            published_at=_maybe_date(value.get("published_at")),
            event_at=_maybe_date(value.get("event_at")),
            passage=_maybe_string(value.get("passage")),
            canonical_entity_iris=tuple(
                str(item) for item in value.get("canonical_entity_iris", [])
            ),
            updated_at=_maybe_date(value.get("updated_at")),
            ingested_at=_maybe_date(value.get("ingested_at")),
            publication_year=value.get("publication_year"),
            publication_precision=value.get("publication_precision"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid evidence catalog entry") from error


def _date(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("datetime is required")
    return datetime.fromisoformat(value)


def _maybe_date(value: object) -> datetime | None:
    return None if value is None else _date(value)


def _maybe_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Cannot serialize {type(value).__name__}")
