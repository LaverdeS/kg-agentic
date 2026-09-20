# EURIO data inventory and first-corpus baseline

This is the durable local reference for the exploratory data analysis (EDA) recorded on issue #3.
It defines the measurements used to choose the first local corpus and separates observed values from
values that have not been measured. The EDA script, downloaded data, JSON summary, and static
dashboard remain local-only under `.scratch/eda/cement/`.

Measurements were taken on 2026-09-20 from the official [EURIO SPARQL endpoint](https://cordis.europa.eu/datalab/sparql-api)
and the [EURIO distribution catalogue](https://data.europa.eu/api/hub/search/datasets/named-graphs-from-eurio-knowledge-graph).

## Terms and measurement boundary

| Term | Meaning in this project |
| --- | --- |
| Global source graph | All EURIO records available from the public endpoint. It is not copied into this repository or loaded into local Neo4j. |
| Discovery candidate | A project matching the documented high-precision lexical filter. It is a review candidate, not evidence of relevance or capability. |
| Retained corpus | Source versions intentionally kept for the runnable slice: three project records and up to two result-metadata records per project. |
| Evidence record | One versioned source document with its URL, canonical identifiers, content hash, dates, passage, retrieval time, and ingestion time. |
| Graphiti episode | The stored semantic-memory representation of one retained evidence record. |
| Neo4j store | The local database files used by Graphiti, including data, indexes, transaction logs, and database overhead. |
| Durable 10 GB limit | Processed retained corpus plus retained source documents. Raw downloads, expanded RDF, temporary files, Graphiti storage, and Neo4j overhead are measured separately. |

## Measured snapshot

### Global EURIO source inventory

| Metric | Value | What it counts |
| --- | ---: | --- |
| RDF triples | 26,429,912 | Subject-predicate-object statements in EURIO. |
| Distinct subjects | 2,852,747 | Unique resources used as statement subjects. |
| Distinct predicates | 260 | Unique relationship/property types. |
| Distinct objects | 8,999,213 | Unique values or resources used as statement objects. |
| Projects | 80,208 | EURIO project entities. |
| Organisations | 72,534 | EURIO organisation entities. |
| Organisation roles | 399,227 | Role records connecting organisations and projects. |
| Results | 696,156 | EURIO result entities. |
| Projects with start and end dates | 79,246 (98.8%) | Project records with both date fields. |
| Projects with at least one result | 64,928 (80.9%) | Projects connected to a result entity. |
| Projects with at least one organisation role | 78,311 (97.6%) | Projects connected to an organisation through a role. |

These counts describe source coverage; they do not establish project quality, organisational capability,
or result quality.

### First retained corpus

| Metric | Value | Meaning |
| --- | ---: | --- |
| Discovery candidates | 265 | Projects matching `cement|lime` and `capture|ccs|ccus|decarbon` in title or abstract. |
| Reviewed seed projects | 3 | CEMCAP (641185), LEILAC2 (884170), and HERCCULES (101096691). |
| Checked project-role-organisation-result paths | 3 of 3 | Each seed has one manually checked multi-hop EURIO path. |
| Retained source versions | 9 | Three project records and six result-metadata records. |
| Project records with body text | 3 | Project abstract passages; they are source-reported objectives, not proof of outcomes. |
| Result records with body text | 0 of 6 | The retained result rows are identifier/title metadata only. |
| Defensible publication timestamps | 0 of 9 | This is why the application only supports current investigations. |
| Distinct content-hash versions | 9 | No duplicate version was observed in the first corpus. |
| Reingestion result | 0 added, 9 skipped | The second live ingestion recognized every retained version as unchanged. |

No organisation-led expansion is used. The first graph only follows seed project to role/organisation and
seed project to result. This prevents a high-degree organisation from silently bringing unrelated work
into the corpus.

### Local graph and storage

| Layer | Measured size | Interpretation |
| --- | ---: | --- |
| Retained raw source files and version index | 11,740 bytes | The source material retained by the runnable implementation after live ingestion. |
| Earlier processed-text estimate | 10,433 bytes / about 1,080 tokens | EDA estimate before live ingestion; use the retained-file measure above for current disk use. |
| Graphiti ingestion | 9 episodes | One episode was added for each retained source version. |
| Neo4j `/data` directory | 542,264,457 bytes | Database, indexes, transaction files, and baseline container/database overhead together; this is not raw evidence size. |
| Durable corpus budget | 10,000,000,000 bytes | Retained source material is far below this boundary. |

Yes, a local graph exists: Neo4j contains the Graphiti episodes and the entities/relationships extracted
from them, and the live investigation retrieves from that graph. It is an evidence-memory graph for nine
source versions, not a local copy of all EURIO relationships. Structural EURIO paths are retrieved live
from the official endpoint and included in the investigation trace.

## Source-download context

The publisher’s catalogue does not state distribution file sizes. On the measurement date, HTTP headers
reported 1,184,126,176 compressed bytes for the complete EURIO N-Quads dump and 1,021,875,675 compressed
bytes for the three named N-Quads graphs combined. They are alternative download paths, not sizes to add
together. Neither was retained locally for this slice.

## Known gaps and their meaning

| Unmeasured item | Why it is unmeasured | Consequence |
| --- | --- | --- |
| Expanded RDF bytes | Requires an explicit full download and expansion. | The compressed-download number must not be used as a local import-size estimate. |
| Global connected components | Requires a complete role-edge extract, not aggregate SPARQL counts. | We cannot yet quantify disconnected groups or hub dominance across all EURIO. |
| Separate Graphiti episode and Neo4j index sizes | Neo4j reports the combined store footprint. | The 542 MB figure is an upper bound for the local database layer, not a per-record cost. |
| Public deliverable and publication text | This first corpus only includes project records and result metadata. | The current brief must distinguish objectives and metadata from demonstrated results. |

These limits are active safeguards. The application rejects historical `--as-of` questions rather than
using current records, and citation checks prevent a generated statement without retrieved evidence from
appearing as a supported statement.

## Reproduce the runnable-slice measurements

```powershell
docker compose up -d neo4j
uv run kg-agentic ingest
uv run kg-agentic investigate --json

$env:RUN_LIVE = "1"
uv run pytest tests/test_live_stack.py -q
```

The issue record contains the alignment decisions, EDA snapshot, and live-run evidence:
[alignment](https://github.com/LaverdeS/kg-agentic/issues/3#issuecomment-5749530263),
[EDA snapshot](https://github.com/LaverdeS/kg-agentic/issues/3#issuecomment-5749658626), and
[live implementation update](https://github.com/LaverdeS/kg-agentic/issues/3#issuecomment-5751273751).
