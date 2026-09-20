import os

import pytest
from dotenv import load_dotenv

from kg_agentic.application.cement import CURRENT_QUESTION
from kg_agentic.cli import _ingest
from kg_agentic.infrastructure.bootstrap import investigate_cement_slice
from kg_agentic.infrastructure.runtime import Settings
from kg_agentic.knowledge.models import InvestigationRequest


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_eurio_graphiti_neo4j_stack() -> None:
    load_dotenv()
    if os.getenv("RUN_LIVE") != "1":
        pytest.skip("set RUN_LIVE=1 to run the EURIO/Graphiti/Neo4j smoke test")
    settings = Settings.from_environment()
    assert await _ingest() == 0
    result, _usage = await investigate_cement_slice(
        settings, InvestigationRequest(question=CURRENT_QUESTION)
    )
    assert len(result.paths) == 3
    assert result.evidence
    assert result.status == "completed"
