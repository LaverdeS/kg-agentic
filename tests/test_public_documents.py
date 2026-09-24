import json
from pathlib import Path

from kg_agentic.application.cement import (
    CORPUS_ID,
    FROZEN_CORPUS_ID,
    FROZEN_PROJECT_IRIS,
    FROZEN_PUBLIC_EVIDENCE,
    LIVE_PROJECT_IRIS,
    LIVE_PUBLIC_EVIDENCE,
)
from kg_agentic.infrastructure.eurio import EurioEvidenceSource
from kg_agentic.infrastructure.public_documents import PublicEvidenceSource
from kg_agentic.knowledge.models import PublicEvidenceSpec


class RecordedEurioQueryClient:
    async def query(self, sparql: str) -> dict:
        fixture_name = (
            "eurio_project_records.json" if "?abstract" in sparql else "eurio_results.json"
        )
        fixture = Path(__file__).parent / "fixtures" / fixture_name
        return json.loads(fixture.read_text(encoding="utf-8"))


class RecordedDocumentClient:
    async def fetch(self, url: str) -> bytes:
        if url == "https://publisher.example/publication.pdf":
            return b"%PDF-reviewed-publication"
        return f"%PDF-reviewed:{url}".encode()


async def test_public_full_text_keeps_source_bytes_distinct_from_metadata() -> None:
    source = PublicEvidenceSource(RecordedDocumentClient())
    documents = await source.fetch_documents(
        (
            PublicEvidenceSpec(
                dataset_id="source",
                corpus_id="corpus",
                source_id="publication-1",
                source_url="https://publisher.example/publication.pdf",
                source_category="publication_full_text",
                text="A reviewed passage from the publication.",
                passage="Printed page 1.",
                canonical_entity_iris=("source:project/1",),
                publication_year=2020,
                publication_precision="year",
            ),
        )
    )

    document = documents[0]
    assert document.source_category == "publication_full_text"
    assert document.kind.value == "source_claim"
    assert document.raw_payload == b"%PDF-reviewed-publication"
    assert document.text == "A reviewed passage from the publication."
    assert (document.publication_year, document.publication_precision) == (2020, "year")


async def test_cement_seed_has_all_four_source_categories_with_retained_full_text() -> None:
    eurio_documents = await EurioEvidenceSource(
        RecordedEurioQueryClient(), corpus_id="cement-retrofit-v1"
    ).fetch_documents(project_iris=FROZEN_PROJECT_IRIS, results_per_project=1)
    public_documents = await PublicEvidenceSource(RecordedDocumentClient()).fetch_documents(
        FROZEN_PUBLIC_EVIDENCE
    )

    documents = (*eurio_documents, *public_documents)

    assert {document.source_category for document in documents} >= {
        "project_record",
        "result_metadata",
        "public_deliverable_full_text",
        "publication_full_text",
    }
    deliverable = next(
        document
        for document in documents
        if document.source_category == "public_deliverable_full_text"
    )
    assert "zenodo.org/records/2593240/files/" in deliverable.source_url
    assert deliverable.raw_payload is not None
    assert deliverable.canonical_entity_iris == (FROZEN_PROJECT_IRIS[0],)
    assert "p. iii" in deliverable.passage
    assert deliverable.publication_year == 2018
    assert deliverable.publication_precision == "year"


def test_live_corpus_is_separate_and_materially_larger_than_the_frozen_benchmark() -> None:
    assert CORPUS_ID != FROZEN_CORPUS_ID
    assert len(FROZEN_PROJECT_IRIS) == 3
    assert len(LIVE_PROJECT_IRIS) == 6
    assert len(FROZEN_PUBLIC_EVIDENCE) == 2
    assert len(LIVE_PUBLIC_EVIDENCE) == 5
