# ruff: noqa: E501
"""A deterministic, source-labelled snapshot for local UI testing.

It is deliberately a recorded display fixture, not a replacement for a live
investigation.  Live mode below calls the existing application composition.
"""

from datetime import UTC, datetime

from kg_agentic.application.cement import (
    CEMCAP_AMMONIA_PUBLICATION,
    CEMCAP_D45_DELIVERABLE,
    CORPUS_ID,
    CURRENT_QUESTION,
    SEED_PROJECTS,
)
from kg_agentic.knowledge.models import (
    Citation,
    EvidenceItem,
    EvidenceKind,
    InvestigationPlan,
    InvestigationResult,
    RecommendationBrief,
    Relationship,
    StructuralPath,
    SupportedClaim,
    TraceStep,
)


def recorded_result() -> InvestigationResult:
    retrieved_at = datetime(2026, 9, 20, tzinfo=UTC)
    paths = tuple(
        _path(project, role, result)
        for project, role, result in zip(
            SEED_PROJECTS,
            (
                ("9a23d532-9720-3e20-9ada-6b2fd6225b8d", "thirdParty"),
                ("53dfc3f1-c10c-3844-8c6a-187c335d73f4", "thirdParty"),
                ("6b57a172-29c5-3b39-afd1-10b6c3e004cd", "coordinator"),
            ),
            (
                "2cc39403-e975-327f-8657-8df803af027d",
                "461c02da-5450-3ad1-ba61-10d85f5c4583",
                "2d34f8d6-c3ec-3593-8bb1-12e4a264a6a9",
            ),
            strict=True,
        )
    )
    evidence = (
        EvidenceItem(
            id="cordis:cemcap:project-record:recorded",
            corpus_id=CORPUS_ID,
            kind=EvidenceKind.SOURCE_CLAIM,
            text="CEMCAP compares capture technologies for cement-plant applications.",
            source_url="https://cordis.europa.eu/project/id/641185",
            source_category="project_record",
            content_hash="recorded:cemcap-project",
            retrieved_at=retrieved_at,
            published_at=None,
            event_at=None,
            passage="Recorded CORDIS project record used for the local explorer.",
            canonical_entity_iris=(SEED_PROJECTS[0].iri,),
        ),
        EvidenceItem(
            id="cordis:herccules:project-record:recorded",
            corpus_id=CORPUS_ID,
            kind=EvidenceKind.SOURCE_CLAIM,
            text="HERCCULES reporting described planned pilot validation, not experimental results.",
            source_url="https://cordis.europa.eu/project/id/101096691/reporting",
            source_category="project_record",
            content_hash="recorded:herccules-project",
            retrieved_at=retrieved_at,
            published_at=None,
            event_at=None,
            passage="The reporting-period record says experimental results were not yet available.",
            canonical_entity_iris=(SEED_PROJECTS[2].iri,),
        ),
        EvidenceItem(
            id="publication:perez-calvo-2018:recorded",
            corpus_id=CORPUS_ID,
            kind=EvidenceKind.SOURCE_CLAIM,
            text=CEMCAP_AMMONIA_PUBLICATION.text,
            source_url=CEMCAP_AMMONIA_PUBLICATION.source_url,
            source_category=CEMCAP_AMMONIA_PUBLICATION.source_category,
            content_hash="recorded:perez-calvo-2018",
            retrieved_at=retrieved_at,
            published_at=None,
            event_at=None,
            passage=CEMCAP_AMMONIA_PUBLICATION.passage,
            canonical_entity_iris=CEMCAP_AMMONIA_PUBLICATION.canonical_entity_iris,
            publication_year=2018,
            publication_precision="year",
        ),
        EvidenceItem(
            id="deliverable:cemcap-d4.5-v1:recorded",
            corpus_id=CORPUS_ID,
            kind=EvidenceKind.SOURCE_CLAIM,
            text=CEMCAP_D45_DELIVERABLE.text,
            source_url=CEMCAP_D45_DELIVERABLE.source_url,
            source_category=CEMCAP_D45_DELIVERABLE.source_category,
            content_hash="recorded:cemcap-d4.5-v1",
            retrieved_at=retrieved_at,
            published_at=None,
            event_at=None,
            passage=CEMCAP_D45_DELIVERABLE.passage,
            canonical_entity_iris=CEMCAP_D45_DELIVERABLE.canonical_entity_iris,
            publication_year=2018,
            publication_precision="year",
        ),
    )
    citations = {item.id: _citation(item) for item in evidence}
    brief = RecommendationBrief(
        decision=_claim(
            "Prioritise a bounded retrofit feasibility study.", citations, evidence[0].id
        ),
        recommendation=_claim(
            "Shortlist the CEMCAP-linked ammonia-capture evidence for site-specific validation.",
            citations,
            evidence[2].id,
        ),
        alternatives=(
            _claim(
                "Keep HERCCULES as a validation path, not demonstrated-performance proof.",
                citations,
                evidence[1].id,
            ),
        ),
        uncertainty=_claim(
            "Reported comparisons may use incompatible capture, utility, and cost boundaries.",
            citations,
            evidence[0].id,
        ),
        next_action=_claim(
            "Request plant-specific utilities, capture boundary, and current pilot evidence.",
            citations,
            evidence[1].id,
        ),
        claims=(
            _claim(
                "The retained publication reports pilot tests, not commercial-scale operation.",
                citations,
                evidence[2].id,
            ),
        ),
    )
    return InvestigationResult(
        status="completed",
        plan=InvestigationPlan(
            question=CURRENT_QUESTION,
            actions=(
                "Inspect organization-project-output paths for the configured seed corpus.",
                "Retrieve corpus-scoped semantic evidence relevant to the decision.",
                "Check that every displayed material statement has a source citation.",
            ),
        ),
        trace=(
            TraceStep(action="plan", count=3),
            TraceStep(action="retrieve_structural_paths", count=3),
            TraceStep(action="retrieve_semantic_evidence", count=3),
            TraceStep(action="check_support", count=6, detail="completed"),
        ),
        paths=paths,
        evidence=evidence,
        brief=brief,
        gaps=(
            "This recorded UX snapshot is current-only; historical requests remain unsupported.",
        ),
    )


def _path(project, role_data: tuple[str, str], result_id: str) -> StructuralPath:
    role_id, role_label = role_data
    role_iri = f"http://data.europa.eu/s66/resource/organisationroles/{role_id}"
    organisation_iri = (
        "http://data.europa.eu/s66/resource/organisations/5ddbaa23-06d6-39f8-8b9f-9fd78d53f149"
    )
    result_iri = f"http://data.europa.eu/s66/resource/results/{result_id}"
    source_url = f"https://cordis.europa.eu/project/id/{project.grant_id}"
    return StructuralPath(
        relationships=(
            Relationship(
                project.iri, "hasInvolvedParty", role_iri, source_url, (("roleLabel", role_label),)
            ),
            Relationship(
                role_iri, "isRoleOf", organisation_iri, source_url, (("roleLabel", role_label),)
            ),
            Relationship(project.iri, "hasResult", result_iri, source_url),
        )
    )


def _citation(item: EvidenceItem) -> Citation:
    return Citation(
        item.id, item.source_url, item.source_category, item.passage or "", item.content_hash
    )


def _claim(text: str, citations: dict[str, Citation], evidence_id: str) -> SupportedClaim:
    return SupportedClaim(text=text, citations=(citations[evidence_id],))
