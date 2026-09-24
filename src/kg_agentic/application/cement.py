from dataclasses import dataclass

from kg_agentic.knowledge.models import PublicEvidenceSpec

DATASET_ID = "cordis-eurio"
FROZEN_CORPUS_ID = "cement-retrofit-v1"
LIVE_CORPUS_ID = "cement-industrial-decarbonisation-v2"


@dataclass(frozen=True, slots=True)
class SeedProject:
    acronym: str
    grant_id: str
    iri: str


FROZEN_SEED_PROJECTS = (
    SeedProject(
        "CEMCAP",
        "641185",
        "http://data.europa.eu/s66/resource/projects/91b4e591-b2dd-357a-9556-45feba981888",
    ),
    SeedProject(
        "LEILAC2",
        "884170",
        "http://data.europa.eu/s66/resource/projects/a3628245-f605-33d4-81ec-10086462f8a1",
    ),
    SeedProject(
        "HERCCULES",
        "101096691",
        "http://data.europa.eu/s66/resource/projects/4bdcdbb5-0dac-357a-94e6-98df709eccad",
    ),
)

# CLEANKER shares seven EURIO organisation nodes with CEMCAP. Carbon4Minerals and CO2Valorize
# extend the consulting decision to mineralisation/binder pathways without claiming a direct link.
LIVE_SEED_PROJECTS = (
    *FROZEN_SEED_PROJECTS,
    SeedProject(
        "CLEANKER",
        "764816",
        "http://data.europa.eu/s66/resource/projects/6e34d1a7-a5fc-3206-9b1d-318bed02bd81",
    ),
    SeedProject(
        "Carbon4Minerals",
        "101091870",
        "http://data.europa.eu/s66/resource/projects/d82071df-349a-32ff-b5e5-c400815a4d1d",
    ),
    SeedProject(
        "CO2Valorize",
        "101073547",
        "http://data.europa.eu/s66/resource/projects/a2674158-71f8-3bc6-a339-4cfff77ce309",
    ),
)

FROZEN_PROJECT_IRIS = tuple(project.iri for project in FROZEN_SEED_PROJECTS)
LIVE_PROJECT_IRIS = tuple(project.iri for project in LIVE_SEED_PROJECTS)


def _public_evidence(
    corpus_id: str, projects: tuple[SeedProject, ...]
) -> tuple[PublicEvidenceSpec, ...]:
    by_acronym = {project.acronym: project for project in projects}
    common = (
        PublicEvidenceSpec(
            DATASET_ID,
            corpus_id,
            "deliverable-cemcap-d4-5-v1",
            "https://zenodo.org/records/2593240/files/d4.5-retrofitability-study-for-co2-capture-technologies-in-cement-plants---revision-1.pdf?download=1",
            "public_deliverable_full_text",
            (
                "The CEMCAP D4.5 public deliverable compares retrofitability using process impact, "
                "equipment footprint, utilities, new chemicals, and operational experience. It "
                "explicitly excludes economic assessment, so it cannot rank technologies on "
                "cost or select a supplier."
            ),
            (
                "D4.5 PDF, p. iii (scope) and p. 2 (site-specific comparison limitation); "
                "Zenodo record 2593240, v1."
            ),
            (by_acronym["CEMCAP"].iri,),
            publication_year=2018,
            publication_precision="year",
        ),
        PublicEvidenceSpec(
            DATASET_ID,
            corpus_id,
            "publication-perez-calvo-2018",
            "https://www.aidic.it/cet/18/69/025.pdf",
            "publication_full_text",
            (
                "The publication reports pilot tests and rate-based modelling of CO2 capture in "
                "cement plants using aqueous ammonia. It describes experiments with synthetic "
                "flue gases reproducing cement-plant conditions and does not establish "
                "commercial-scale operation."
            ),
            "Title and abstract, printed p. 145; pilot-test scope, printed pp. 145-146.",
            (by_acronym["CEMCAP"].iri,),
            publication_year=2018,
            publication_precision="year",
        ),
    )
    if corpus_id == FROZEN_CORPUS_ID:
        return common
    return (
        *common,
        PublicEvidenceSpec(
            DATASET_ID,
            corpus_id,
            "cordis-cleanker-reporting",
            "https://cordis.europa.eu/project/id/764816/reporting",
            "cordis_reporting_full_text",
            (
                "CORDIS describes CLEANKER as demonstrating calcium looping for cement "
                "production in a highly integrated configuration. Its project objective includes "
                "an entrained-flow "
                "carbonator and oxyfuel calciner demonstration, scale-up, economic, lifecycle, "
                "transport/storage/utilisation, and exploitation work."
            ),
            "CORDIS CLEANKER reporting page, project objective and public reporting summary.",
            (by_acronym["CLEANKER"].iri,),
        ),
        PublicEvidenceSpec(
            DATASET_ID,
            corpus_id,
            "cordis-carbon4minerals-reporting",
            "https://cordis.europa.eu/project/id/101091870/reporting",
            "cordis_reporting_full_text",
            (
                "CORDIS reports Carbon4Minerals pilots spanning capture, cement production, and "
                "low-carbon construction products. It reports that environmental and economic "
                "feasibility are being assessed; this is project-reported progress, not an "
                "independent proof of "
                "commercial performance."
            ),
            (
                "CORDIS Carbon4Minerals periodic-reporting summary; reporting period 2024-01-01 to "
                "2025-06-30."
            ),
            (by_acronym["Carbon4Minerals"].iri,),
        ),
        PublicEvidenceSpec(
            DATASET_ID,
            corpus_id,
            "cordis-co2valorize-results",
            "https://cordis.europa.eu/project/id/101073547/results",
            "cordis_results_page_full_text",
            (
                "CORDIS describes CO2Valorize as investigating captured-CO2 carbonation of "
                "supplementary cementitious materials from mine tailings and recycled concrete. "
                "The stated 50 percent per-tonne reduction is a project objective/proof-of-concept "
                "target, not a "
                "verified site-specific outcome."
            ),
            "CORDIS CO2Valorize results page, project objective and linked-result listing.",
            (by_acronym["CO2Valorize"].iri,),
        ),
    )


FROZEN_PUBLIC_EVIDENCE = _public_evidence(FROZEN_CORPUS_ID, FROZEN_SEED_PROJECTS)
LIVE_PUBLIC_EVIDENCE = _public_evidence(LIVE_CORPUS_ID, LIVE_SEED_PROJECTS)

# Live product aliases. Frozen benchmark callers use explicit FROZEN_* configuration.
CORPUS_ID = LIVE_CORPUS_ID
GROUP_ID = f"{DATASET_ID}:{CORPUS_ID}"
SEED_PROJECTS = LIVE_SEED_PROJECTS
PROJECT_IRIS = LIVE_PROJECT_IRIS
PUBLIC_EVIDENCE = LIVE_PUBLIC_EVIDENCE
CURRENT_QUESTION = (
    "Which capture, calcium-looping, and mineralisation pathways should a cement producer take "
    "into a site-specific feasibility study, and what public evidence still prevents a direct "
    "cost or commercial-readiness ranking?"
)
