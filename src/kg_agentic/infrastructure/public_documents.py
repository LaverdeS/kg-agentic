"""HTTP acquisition for already-reviewed public evidence documents."""

import ssl
from datetime import UTC, datetime
from typing import Protocol

import httpx
import truststore

from kg_agentic.knowledge.models import (
    EvidenceKind,
    PublicEvidenceSpec,
    SourceDocument,
)


class DocumentClient(Protocol):
    async def fetch(self, url: str) -> bytes: ...


class HttpDocumentClient:
    """Fetch source bytes with the platform trust store and no credential forwarding."""

    async def fetch(self, url: str) -> bytes:
        ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=ssl_context,
        ) as client:
            response = await client.get(url, headers={"Accept": "application/pdf"})
            response.raise_for_status()
            return response.content


class PublicEvidenceSource:
    """Retain versioned public-document bytes without treating metadata as full text."""

    def __init__(self, client: DocumentClient | None = None) -> None:
        self._client = client or HttpDocumentClient()

    async def fetch_documents(
        self, specs: tuple[PublicEvidenceSpec, ...]
    ) -> tuple[SourceDocument, ...]:
        retrieved_at = datetime.now(UTC)
        documents: list[SourceDocument] = []
        for spec in specs:
            raw_payload = await self._client.fetch(spec.source_url)
            if not raw_payload:
                raise ValueError(f"Public evidence was empty: {spec.source_url}")
            documents.append(
                SourceDocument(
                    dataset_id=spec.dataset_id,
                    corpus_id=spec.corpus_id,
                    source_id=spec.source_id,
                    source_url=spec.source_url,
                    source_category=spec.source_category,
                    text=spec.text,
                    passage=spec.passage,
                    kind=EvidenceKind.SOURCE_CLAIM,
                    canonical_entity_iris=spec.canonical_entity_iris,
                    publication_at=spec.publication_at,
                    update_at=None,
                    event_at=None,
                    retrieved_at=retrieved_at,
                    raw_payload=raw_payload,
                    publication_year=spec.publication_year,
                    publication_precision=spec.publication_precision,
                )
            )
        return tuple(documents)
