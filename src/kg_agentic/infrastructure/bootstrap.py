"""Composition root for the one real EURIO/Graphiti investigation slice."""

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from kg_agentic.application.cement import (
    CORPUS_ID,
    FROZEN_CORPUS_ID,
    FROZEN_PROJECT_IRIS,
    GROUP_ID,
    PROJECT_IRIS,
    PUBLIC_EVIDENCE,
)
from kg_agentic.application.evaluation import (
    EvaluationQuestion,
    EvaluationReport,
    evaluate_questions,
)
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
    DraftBrief,
    EvidenceItem,
    InvestigationComparison,
    InvestigationPlan,
    InvestigationRequest,
    InvestigationResult,
    StructuralPath,
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
    settings: Settings,
    request: InvestigationRequest,
    *,
    corpus_id: str = CORPUS_ID,
    group_id: str = GROUP_ID,
    project_iris: tuple[str, ...] = PROJECT_IRIS,
) -> tuple[InvestigationResult, dict[str, int]]:
    """Run a current or strict historical investigation through the concrete live adapters."""
    runtime = build_runtime(settings)
    try:
        corpus_dir = settings.data_dir / "cordis-eurio" / corpus_id
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
            project_iris=project_iris,
            corpus_id=group_id,
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


async def evaluate_cement_slice(
    settings: Settings,
    questions: Sequence[EvaluationQuestion],
    *,
    corpus_id: str = FROZEN_CORPUS_ID,
    project_iris: tuple[str, ...] = FROZEN_PROJECT_IRIS,
) -> EvaluationReport:
    """Compare the concrete full slice with deliberately narrower retrieval baselines."""

    async def full_agent(
        request: InvestigationRequest,
    ) -> tuple[InvestigationResult, dict[str, int]]:
        return await investigate_cement_slice(
            settings,
            request,
            corpus_id=corpus_id,
            group_id=f"cordis-eurio:{corpus_id}",
            project_iris=project_iris,
        )

    async def eurio_only(
        request: InvestigationRequest,
    ) -> tuple[InvestigationResult, dict[str, int]]:
        agent = InvestigationAgent(
            structural_source=EurioStructuralSource(HttpSparqlQueryClient()),
            evidence_memory=_NoEvidenceMemory(),
            brief_generator=_UnexpectedBriefGenerator(),
            project_iris=project_iris,
            corpus_id=f"cordis-eurio:{corpus_id}",
            evidence_limit=settings.evidence_limit,
        )
        return await agent.investigate(request), {}

    async def semantic_only(
        request: InvestigationRequest,
    ) -> tuple[InvestigationResult, dict[str, int]]:
        runtime = build_runtime(settings)
        try:
            corpus_dir = settings.data_dir / "cordis-eurio" / corpus_id
            generator = OpenAIBriefGenerator(
                runtime.openai,
                model=settings.model,
                max_output_tokens=settings.model_max_output_tokens,
            )
            agent = InvestigationAgent(
                structural_source=_NoStructuralSource(),
                evidence_memory=GraphitiEvidenceMemory(
                    runtime.graphiti,
                    historical_catalog=JsonEvidenceCatalog(corpus_dir / "evidence.json"),
                ),
                brief_generator=generator,
                project_iris=project_iris,
                corpus_id=f"cordis-eurio:{corpus_id}",
                evidence_limit=settings.evidence_limit,
            )
            return await agent.investigate(request), generator.last_usage
        finally:
            await runtime.close()

    return await evaluate_questions(
        questions=questions,
        runners={
            "agent": full_agent,
            "eurio_only": eurio_only,
            "semantic_only": semantic_only,
        },
        baseline_notes={
            "agent": "EURIO structural paths plus corpus-scoped Graphiti semantic evidence.",
            "eurio_only": (
                "EURIO typed paths only. It deliberately has no source-text evidence and must "
                "abstain rather than present metadata or participation as a cited recommendation."
            ),
            "semantic_only": (
                "Graphiti semantic evidence only. It uses the same corpus and temporal gate but "
                "does not retrieve EURIO organisation-project-output paths."
            ),
        },
    )


def frozen_cement_source_versions(settings: Settings) -> list[str]:
    """Reject corpus drift before comparing the fixed #6 benchmark."""
    baseline_path = Path("evals/cement-retrofit-v1-baseline.json")
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        expected = baseline["source_versions"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"Invalid frozen evaluation baseline: {baseline_path}") from error
    if (
        not isinstance(baseline, dict)
        or baseline.get("dataset_id") != "cordis-eurio"
        or baseline.get("corpus_id") != FROZEN_CORPUS_ID
        or not isinstance(expected, list)
        or not all(isinstance(item, str) for item in expected)
    ):
        raise ValueError(f"Invalid frozen evaluation baseline: {baseline_path}")
    version_path = settings.data_dir / "cordis-eurio" / FROZEN_CORPUS_ID / "versions.json"
    if not version_path.exists():
        actual: list[str] = []
    else:
        value = json.loads(version_path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Invalid source-version index: {version_path}")
        actual = value
    if set(actual) != set(expected) or len(actual) != len(expected):
        missing = sorted(set(expected).difference(actual))
        unexpected = sorted(set(actual).difference(expected))
        raise ValueError(
            "The local corpus does not match the frozen #6 benchmark "
            f"(missing={missing}, unexpected={unexpected})"
        )
    return expected


class _NoEvidenceMemory:
    async def search(
        self, *, query: str, corpus_id: str, limit: int, as_of: datetime | None = None
    ) -> tuple[EvidenceItem, ...]:
        return ()


class _NoStructuralSource:
    async def find_paths(
        self, *, project_iris: tuple[str, ...], as_of: datetime | None = None
    ) -> tuple[StructuralPath, ...]:
        return ()


class _UnexpectedBriefGenerator:
    async def generate(
        self,
        *,
        question: str,
        plan: InvestigationPlan,
        paths: tuple[StructuralPath, ...],
        evidence: tuple[EvidenceItem, ...],
    ) -> DraftBrief:
        raise AssertionError("EURIO-only evaluation must abstain before generation")


def _sum_usage(*usages: dict[str, int]) -> dict[str, int]:
    keys = {key for usage in usages for key in usage}
    return {key: sum(usage.get(key, 0) for usage in usages) for key in keys}
