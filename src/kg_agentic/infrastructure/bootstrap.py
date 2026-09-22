"""Composition root for the one real EURIO/Graphiti investigation slice."""

from kg_agentic.application.cement import CORPUS_ID, GROUP_ID, PROJECT_IRIS, PUBLIC_EVIDENCE
from kg_agentic.application.investigation import InvestigationAgent, unsupported_historical_result
from kg_agentic.infrastructure.eurio import (
    EurioEvidenceSource,
    EurioStructuralSource,
    HttpSparqlQueryClient,
)
from kg_agentic.infrastructure.graphiti_adapter import GraphitiEvidenceMemory
from kg_agentic.infrastructure.openai_brief import OpenAIBriefGenerator
from kg_agentic.infrastructure.public_documents import PublicEvidenceSource
from kg_agentic.infrastructure.runtime import Settings, build_runtime
from kg_agentic.knowledge.ingestion import (
    FileSourceArchive,
    IngestionPipeline,
    IngestionReport,
    JsonVersionIndex,
)
from kg_agentic.knowledge.models import InvestigationRequest, InvestigationResult


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
        pipeline = IngestionPipeline(
            episode_sink=GraphitiEvidenceMemory(runtime.graphiti),
            version_index=JsonVersionIndex(corpus_dir / "versions.json"),
            archive=FileSourceArchive(corpus_dir / "raw"),
        )
        return await pipeline.ingest(tuple(documents))
    finally:
        await runtime.close()


async def investigate_cement_slice(
    settings: Settings, request: InvestigationRequest
) -> tuple[InvestigationResult, dict[str, int]]:
    """Run the current-only investigation through the concrete live adapters."""
    if request.as_of is not None:
        return unsupported_historical_result(request.question, request.as_of), {}
    runtime = build_runtime(settings)
    try:
        generator = OpenAIBriefGenerator(
            runtime.openai,
            model=settings.model,
            max_output_tokens=settings.model_max_output_tokens,
        )
        agent = InvestigationAgent(
            structural_source=EurioStructuralSource(HttpSparqlQueryClient()),
            evidence_memory=GraphitiEvidenceMemory(runtime.graphiti),
            brief_generator=generator,
            project_iris=PROJECT_IRIS,
            corpus_id=GROUP_ID,
            evidence_limit=settings.evidence_limit,
        )
        result = await agent.investigate(request)
        return result, generator.last_usage
    finally:
        await runtime.close()
