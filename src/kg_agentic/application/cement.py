from dataclasses import dataclass

from kg_agentic.knowledge.models import PublicEvidenceSpec

DATASET_ID = "cordis-eurio"
CORPUS_ID = "cement-retrofit-v1"
GROUP_ID = f"{DATASET_ID}:{CORPUS_ID}"


@dataclass(frozen=True, slots=True)
class SeedProject:
    acronym: str
    grant_id: str
    iri: str


SEED_PROJECTS = (
    SeedProject(
        acronym="CEMCAP",
        grant_id="641185",
        iri="http://data.europa.eu/s66/resource/projects/91b4e591-b2dd-357a-9556-45feba981888",
    ),
    SeedProject(
        acronym="LEILAC2",
        grant_id="884170",
        iri="http://data.europa.eu/s66/resource/projects/a3628245-f605-33d4-81ec-10086462f8a1",
    ),
    SeedProject(
        acronym="HERCCULES",
        grant_id="101096691",
        iri="http://data.europa.eu/s66/resource/projects/4bdcdbb5-0dac-357a-94e6-98df709eccad",
    ),
)

PROJECT_IRIS = tuple(project.iri for project in SEED_PROJECTS)
CURRENT_QUESTION = (
    "Which capture pathways and complementary partners should a cement producer shortlist for "
    "a site-specific retrofit feasibility study, and which reported comparisons have "
    "incompatible capture, utility, or cost boundaries?"
)

# These are full-text, versioned public documents rather than EURIO result metadata. The adapter
# retains their original bytes and the reviewed passages make the limited evidence supplied to
# Graphiti explicit. The sources identify 2018 but not a timestamp suitable for historical
# eligibility, so the current-only slice deliberately retains year precision.
CEMCAP_D45_DELIVERABLE = PublicEvidenceSpec(
    dataset_id=DATASET_ID,
    corpus_id=CORPUS_ID,
    source_id="deliverable-cemcap-d4-5-v1",
    source_url=(
        "https://zenodo.org/records/2593240/files/"
        "d4.5-retrofitability-study-for-co2-capture-technologies-in-cement-plants"
        "---revision-1.pdf?download=1"
    ),
    source_category="public_deliverable_full_text",
    text=(
        "The CEMCAP D4.5 public deliverable compares retrofitability using technical "
        "criteria including process impact, equipment footprint, utilities, new chemicals, "
        "and operational experience. It explicitly excludes economic assessment, so it cannot "
        "rank technologies on cost or select a supplier."
    ),
    passage=(
        "D4.5 PDF, p. iii (scope) and p. 2 (site-specific comparison limitation); "
        "Zenodo record 2593240, v1."
    ),
    canonical_entity_iris=(SEED_PROJECTS[0].iri,),
    publication_year=2018,
    publication_precision="year",
)

CEMCAP_AMMONIA_PUBLICATION = PublicEvidenceSpec(
    dataset_id=DATASET_ID,
    corpus_id=CORPUS_ID,
    source_id="publication-perez-calvo-2018",
    source_url="https://www.aidic.it/cet/18/69/025.pdf",
    source_category="publication_full_text",
    text=(
        "The publication reports pilot tests and rate-based modelling of CO2 capture in cement "
        "plants using aqueous ammonia. It describes experiments with synthetic flue gases "
        "reproducing cement-plant conditions and does not establish commercial-scale operation."
    ),
    passage="Title and abstract, printed p. 145; pilot-test scope, printed pp. 145-146.",
    canonical_entity_iris=(SEED_PROJECTS[0].iri,),
    publication_year=2018,
    publication_precision="year",
)

PUBLIC_EVIDENCE = (CEMCAP_D45_DELIVERABLE, CEMCAP_AMMONIA_PUBLICATION)
