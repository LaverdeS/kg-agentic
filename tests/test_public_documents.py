from kg_agentic.infrastructure.public_documents import PublicEvidenceSource
from kg_agentic.knowledge.models import PublicEvidenceSpec


class RecordedDocumentClient:
    async def fetch(self, url: str) -> bytes:
        assert url == "https://publisher.example/publication.pdf"
        return b"%PDF-reviewed-publication"


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
