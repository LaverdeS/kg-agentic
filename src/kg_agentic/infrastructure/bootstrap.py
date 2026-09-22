"""Composition root for the one real EURIO/Graphiti investigation slice."""

from datetime import datetime

from kg_agentic.application.cement import CORPUS_ID, GROUP_ID, PROJECT_IRIS, PUBLIC_EVIDENCE
from kg_agentic.application.investigation import InvestigationAgent, compare_investigations
from kg_agentic.infrastructure.eurio import (
    EurioEvidenceSource,
    EurioStructuralSource,
    HttpSparqlQueryClient,
)
from kg_agentic.infrastructure.graphiti_adapter import GraphitiEvidenceMemory
from kg_agentic.infrastructure.openai_brief import OpenAIBriefGenerator
from kg_agentic.infrastructure.public_documents import PublicEvidenceSource
from kg_agentic.infrastructure.runtime import Settings, build_runtime
from kg_agentic.knowledge.catalog import JsonEvidenceCatalog
from kg_agentic.knowledge.ingestion import (
    FileSourceArchive,
    IngestionPipeline,
    IngestionReport,
    JsonVersionIndex,
)
from kg_agentic.knowledge.models import (
    InvestigationComparison,
    InvestigationRequest,
    InvestigationResult,
)
from kg_agentic.knowledge.temporal import is_evidence_public_by


async def ingest_cement_slice(settings: Settings) -> IngestionReport:
    """Ingest the fixed seed corpus and its reviewed public deliverable and publication."""
    runtime = build_runtime(settings)
    try:
        await runtime.graphiti.build_indices_and_constraints()
        source = EurioEvidenceSource(HttpSparqlQueryClient(), corpus_id=CORPUS_ID)
        documents = list(
            await source.fetch_documents(project_iris=PROJECT_IRIS, results_per_project=2)
        )
        documents.extend(await PublicEvidenceSource().fetch_documents(PUBLIC_EVIDENCE))
        corpus_dir = settings.data_dir / "cordis-eurio" / CORPUS_ID
        catalog = JsonEvidenceCatalog(corpus_dir / "evidence.json")
        pipeline = IngestionPipeline(
            episode_sink=GraphitiEvidenceMemory(runtime.graphiti),
            version_index=JsonVersionIndex(corpus_dir / "versions.json"),
            archive=FileSourceArchive(corpus_dir / "raw"),
            evidence_catalog=catalog,
        )
        return await pipeline.ingest(tuple(documents))
    finally:
        await runtime.close()


async def investigate_cement_slice(
    settings: Settings, request: InvestigationRequest
) -> tuple[InvestigationResult, dict[str, int]]:
    """Run a current or strict historical investigation through the concrete live adapters."""
    runtime = build_runtime(settings)
    try:
        corpus_dir = settings.data_dir / "cordis-eurio" / CORPUS_ID
        generator = OpenAIBriefGenerator(
            runtime.openai,
            model=settings.model,
            max_output_tokens=settings.model_max_output_tokens,
        )
        agent = InvestigationAgent(
            structural_source=EurioStructuralSource(HttpSparqlQueryClient()),
            evidence_memory=GraphitiEvidenceMemory(
                runtime.graphiti,
                historical_catalog=JsonEvidenceCatalog(corpus_dir / "evidence.json"),
            ),
            brief_generator=generator,
            project_iris=PROJECT_IRIS,
            corpus_id=GROUP_ID,
            evidence_limit=settings.evidence_limit,
        )
        result = await agent.investigate(request)
        return result, generator.last_usage
    finally:
        await runtime.close()


async def compare_cement_slice(
    settings: Settings,
    *,
    question: str,
    earlier_as_of: datetime,
    later_as_of: datetime,
) -> tuple[InvestigationComparison, dict[str, int]]:
    """Compare two strict historical investigations using the same live corpus and limits."""
    earlier, earlier_usage = await investigate_cement_slice(
        settings, InvestigationRequest(question=question, as_of=earlier_as_of)
    )
    later, later_usage = await investigate_cement_slice(
        settings, InvestigationRequest(question=question, as_of=later_as_of)
    )
    catalog = JsonEvidenceCatalog(settings.data_dir / "cordis-eurio" / CORPUS_ID / "evidence.json")
    catalog_items = await catalog.items(corpus_id=GROUP_ID)
    return (
        compare_investigations(
            earlier=earlier,
            earlier_as_of=earlier_as_of,
            later=later,
            later_as_of=later_as_of,
            earlier_eligible_evidence=tuple(
                item for item in catalog_items if is_evidence_public_by(item, earlier_as_of)
            ),
            later_eligible_evidence=tuple(
                item for item in catalog_items if is_evidence_public_by(item, later_as_of)
            ),
        ),
        _sum_usage(earlier_usage, later_usage),
    )


def _sum_usage(*usages: dict[str, int]) -> dict[str, int]:
    keys = {key for usage in usages for key in usage}
    return {key: sum(usage.get(key, 0) for usage in usages) for key in keys}
