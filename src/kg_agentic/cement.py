from dataclasses import dataclass

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
