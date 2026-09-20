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

### Bounded structural acquisition and storage measurement

The accepted measurement path does **not** acquire or retain a full RDF dump. It makes three
suffix HTTP range requests of at most 128 KiB to the official project, organisation, and result
N-Quads ZIP distributions, reads their ZIP central directories, and retains only a JSON summary.
This gives exact compressed and uncompressed member sizes without writing expanded RDF. The
bounded script is ignored at `.scratch/eda/cement/measure_zip_sizes.py`.

| Distribution | Compressed bytes | Expanded RDF bytes |
| --- | ---: | ---: |
| Projects N-Quads | 346,125,030 | 2,303,725,104 |
| Organisations N-Quads | 94,303,133 | 642,177,956 |
| Results N-Quads | 581,447,512 | 2,909,979,534 |
| **Three named graphs** | **1,021,875,675** | **5,855,882,594** |

Observed 2026-09-20 17:58 UTC. The 5.856 GB number is the exact sum of uncompressed ZIP-member
sizes, not a local storage estimate: no expanded RDF was retained, it excludes the remaining
EURIO graph content, and it says nothing about a graph database's import/index overhead.

The connected-component definition is deliberately narrower and reproducible: weak components
over all `eurio:hasInvolvedParty` and `eurio:isRoleOf` IRI edges (project--role--organisation),
not every EURIO RDF predicate. The paired ignored script pages this query in 10,000-row batches
and keeps only union-find counters. On 2026-09-20 the public endpoint did not return its first
ordered page during a six-minute run, so the run was interrupted without a partial count. This is
an explicit endpoint-performance blocker, not a component measurement. Reproduce it with
`.venv\Scripts\python.exe .scratch\eda\cement\measure_bounded_structure.py`; a fresh successful
run is required before using a component or hub-dominance number in a design decision.

### First retained corpus

| Metric | Value | Meaning |
| --- | ---: | --- |
| Discovery candidates | 265 | Projects matching `cement|lime` and `capture|ccs|ccus|decarbon` in title or abstract. |
| Reviewed seed projects | 3 | CEMCAP (641185), LEILAC2 (884170), and HERCCULES (101096691). |
| Checked project-role-organisation-result paths | 3 of 3 | Each seed has one manually checked multi-hop EURIO path. |
| Retained source versions | 10 | Three project records, six result-metadata records, and one versioned public publication. |
| Project records with body text | 3 | Project abstract passages; they are source-reported objectives, not proof of outcomes. |
| Result records with body text | 0 of 6 | The retained result rows are identifier/title metadata only. |
| Public publication with reviewed full-text passage | 1 | A 862,214-byte AIDIC publisher PDF, retained by content hash and marked `publication_full_text`. |
| Defensible publication timestamps | 0 of 10 | The publication supplies only a year and no verified public-release instant; this is why the application only supports current investigations. |
| Distinct content-hash versions | 10 | No duplicate version was observed in the corpus. |
| Reingestion result after publication admission | 0 added, 10 skipped | The next live ingestion recognized every source version as unchanged. |

No organisation-led expansion is used. The first graph only follows seed project to role/organisation and
seed project to result. This prevents a high-degree organisation from silently bringing unrelated work
into the corpus.

### Local graph and storage

| Layer | Measured size | Interpretation |
| --- | ---: | --- |
| Retained raw source files and version index | 874,093 bytes | Ten retained source files plus the version index after the public PDF admission. |
| Earlier processed-text estimate | 10,433 bytes / about 1,080 tokens | EDA estimate before live ingestion; use the retained-file measure above for current disk use. |
| Graphiti ingestion | 10 episodes | One episode was added for each retained source version. |
| Neo4j `/data` directory | 542,927,838 bytes | Database, indexes, transaction files, and baseline container/database overhead together; this is not raw evidence size. |
| Durable corpus budget | 10,000,000,000 bytes | Retained source material is far below this boundary. |

Yes, a local graph exists: Neo4j contains the Graphiti episodes and the entities/relationships extracted
from them, and the live investigation retrieves from that graph. It is an evidence-memory graph for ten
source versions, not a local copy of all EURIO relationships. Structural EURIO paths are retrieved live
from the official endpoint and included in the investigation trace.

## Public-document access

The corpus now contains the publisher-hosted six-page publication
[`10.3303/CET1869025`](https://www.aidic.it/cet/18/69/025.pdf), linked to CEMCAP grant 641185 in
its acknowledgement. The implementation retrieves and retains the original PDF bytes, hashes the
version, and exposes only the explicitly reviewed pilot-test passage to Graphiti. It is therefore
full-text evidence, not metadata-only evidence; its source-reported pilot scope must not be
upgraded to commercial performance.

The CEMCAP D4.5 public-deliverable URL remains a precise reproducible blocker. On 2026-09-20 the
same trust-store-backed adapter used by the application received HTTP 404 from
`https://www.sintef.no/globalassets/project/cemcap/2018-11-14-deliverables/d4.5-retrofitability-study-for-co2-capture-technologies-in-cement-plants.pdf`.
The deliverable is not admitted from search snippets, a historical folder date, or cached metadata.
Its URL, source identity, and access result should be rechecked before any future admission.

## Source-download context

The publisher’s catalogue does not state distribution file sizes. On the measurement date, HTTP headers
reported 1,184,126,176 compressed bytes for the complete EURIO N-Quads dump and 1,021,875,675 compressed
bytes for the three named N-Quads graphs combined. They are alternative download paths, not sizes to add
together. Neither was retained locally for this slice.

## Known gaps and their meaning

| Unmeasured item | Why it is unmeasured | Consequence |
| --- | --- | --- |
| Local graph-import footprint | Requires a separately accepted graph import and index measurement. | The 5.856 GB expanded-RDF figure must not be used as a Neo4j storage estimate. |
| Global connected components | The complete paged public role-edge query did not return its first ordered page during the six-minute bounded run. | We cannot yet quantify disconnected groups or hub dominance; rerun the documented query against a responsive public endpoint or a separately accepted export. |
| Separate Graphiti episode and Neo4j index sizes | Neo4j reports the combined store footprint. | The 542 MB figure is an upper bound for the local database layer, not a per-record cost. |
| Public deliverable text | The official D4.5 URL currently returns HTTP 404 through the application adapter. | Keep it out of the corpus until a retrievable, versioned public source is found. |

These limits are active safeguards. The application rejects historical `--as-of` questions rather than
using current records, and citation checks prevent a generated statement without retrieved evidence from
appearing as a supported statement.

## Reproduce the runnable-slice measurements

```powershell
docker compose up -d neo4j
uv run kg-agentic ingest
uv run kg-agentic investigate --json

.venv\Scripts\python.exe .scratch\eda\cement\measure_zip_sizes.py
.venv\Scripts\python.exe .scratch\eda\cement\measure_bounded_structure.py

$env:RUN_LIVE = "1"
uv run pytest tests/test_live_stack.py -q
```

The issue record contains the alignment decisions, EDA snapshot, and live-run evidence:
[alignment](https://github.com/LaverdeS/kg-agentic/issues/3#issuecomment-5749530263),
[EDA snapshot](https://github.com/LaverdeS/kg-agentic/issues/3#issuecomment-5749658626), and
[live implementation update](https://github.com/LaverdeS/kg-agentic/issues/3#issuecomment-5751273751).
