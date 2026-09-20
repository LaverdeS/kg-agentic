import os

import pytest
from dotenv import load_dotenv

from kg_agentic.cement import CURRENT_QUESTION, GROUP_ID, PROJECT_IRIS
from kg_agentic.cli import _ingest
from kg_agentic.config import Settings, build_runtime
from kg_agentic.eurio import EurioStructuralSource, HttpSparqlQueryClient
from kg_agentic.graphiti_adapter import GraphitiEvidenceMemory


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_eurio_graphiti_neo4j_stack() -> None:
    load_dotenv()
    if os.getenv("RUN_LIVE") != "1":
        pytest.skip("set RUN_LIVE=1 to run the EURIO/Graphiti/Neo4j smoke test")
    settings = Settings.from_environment()
    assert await _ingest() == 0
    paths = await EurioStructuralSource(HttpSparqlQueryClient()).find_paths(
        project_iris=PROJECT_IRIS
    )
    runtime = build_runtime(settings)
    try:
        await runtime.graphiti.build_indices_and_constraints()
        evidence = await GraphitiEvidenceMemory(runtime.graphiti).search(
            query=CURRENT_QUESTION,
            corpus_id=GROUP_ID,
            limit=3,
        )
    finally:
        await runtime.close()
    assert len(paths) == 3
    assert evidence
