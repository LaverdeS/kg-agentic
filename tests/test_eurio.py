import json
from pathlib import Path

import pytest

from kg_agentic.eurio import EurioEvidenceSource, EurioStructuralSource

FIXTURES = Path(__file__).parent / "fixtures"
PROJECTS = (
    "http://data.europa.eu/s66/resource/projects/91b4e591-b2dd-357a-9556-45feba981888",
    "http://data.europa.eu/s66/resource/projects/a3628245-f605-33d4-81ec-10086462f8a1",
    "http://data.europa.eu/s66/resource/projects/4bdcdbb5-0dac-357a-94e6-98df709eccad",
)


class RecordedQueryClient:
    async def query(self, sparql: str):
        if "?abstract" in sparql:
            name = "eurio_project_records.json"
        elif "hasInvolvedParty" in sparql:
            name = "eurio_roles.json"
        else:
            name = "eurio_results.json"
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_eurio_preserves_typed_directed_multi_hop_paths() -> None:
    source = EurioStructuralSource(RecordedQueryClient())

    paths = await source.find_paths(project_iris=PROJECTS)

    assert len(paths) == 3
    assert [edge.predicate for edge in paths[0].relationships] == [
        "http://data.europa.eu/s66#hasInvolvedParty",
        "http://data.europa.eu/s66#isRoleOf",
        "http://data.europa.eu/s66#hasResult",
    ]
    assert paths[0].relationships[0].subject == PROJECTS[0]
    assert paths[0].relationships[1].object.endswith("5ddbaa23-06d6-39f8-8b9f-9fd78d53f149")
    assert paths[0].relationships[2].object.endswith("2cc39403-e975-327f-8657-8df803af027d")


@pytest.mark.asyncio
async def test_eurio_evidence_keeps_record_text_distinct_from_result_metadata() -> None:
    source = EurioEvidenceSource(RecordedQueryClient(), corpus_id="cement-v1")

    documents = await source.fetch_documents(project_iris=PROJECTS, results_per_project=1)

    assert len(documents) == 6
    records = [document for document in documents if document.source_category == "project_record"]
    result_metadata = [
        document for document in documents if document.source_category == "result_metadata"
    ]
    assert len(records) == 3
    assert len(result_metadata) == 3
    assert all(document.publication_at is None for document in documents)
    assert records[0].event_at is not None
    assert records[0].event_at.isoformat().startswith("2015-05-01")
    assert result_metadata[0].text.startswith("Metadata-only EURIO result record:")
    assert result_metadata[0].source_url == result_metadata[0].canonical_entity_iris[1]
    assert result_metadata[0].canonical_entity_iris == (
        PROJECTS[0],
        "http://data.europa.eu/s66/resource/results/2cc39403-e975-327f-8657-8df803af027d",
    )
