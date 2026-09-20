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

# This is full text, not EURIO result metadata: the adapter retains the original PDF bytes and
# this reviewed passage makes the limited evidence supplied to Graphiti explicit.  The publisher
# identifies only the year, so the current-only slice deliberately does not invent a precise
# public-availability timestamp.
PUBLIC_EVIDENCE = (
    PublicEvidenceSpec(
        dataset_id=DATASET_ID,
        corpus_id=CORPUS_ID,
        source_id="publication-perez-calvo-2018",
        source_url="https://www.aidic.it/cet/18/69/025.pdf",
        source_category="publication_full_text",
        text=(
            "The publication reports pilot tests and rate-based modelling of CO2 capture in "
            "cement plants using aqueous ammonia. It describes experiments with synthetic flue "
            "gases reproducing cement-plant conditions and does not establish commercial-scale "
            "operation."
        ),
        passage="Title and abstract, printed p. 145; pilot-test scope, printed pp. 145-146.",
        canonical_entity_iris=(SEED_PROJECTS[0].iri,),
        publication_year=2018,
        publication_precision="year",
    ),
)
