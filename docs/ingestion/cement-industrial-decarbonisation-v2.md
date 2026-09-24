# Connected CORDIS corpus: `cement-industrial-decarbonisation-v2`

This is the live product corpus. It is deliberately separate from the frozen
`cement-retrofit-v1` benchmark: the latter's source-version manifest, raw evaluation JSON, and
committed report are not inputs to this corpus or its post-expansion checks.

## Selection rule

Retain the three original decision-context projects (CEMCAP, LEILAC2, and HERCCULES), then add a
small set only where it strengthens a cement producer's next decision: a retrofit capture route,
an adjacent capture-to-binder route, or a carbonation/SCM route. Every included project has its
official EURIO project record and result metadata ingested. The live source selection is:

| Project | Grant | Reason for inclusion | Connection evidence |
| --- | ---: | --- | --- |
| CEMCAP | 641185 | Original capture-retrofit comparison context | Original seed |
| LEILAC2 | 884170 | Original direct-separation/calcination comparator | Original seed |
| HERCCULES | 101096691 | Original full-chain CCUS and partner context | Original seed |
| CLEANKER | 764816 | Calcium-looping demonstration and scale-up/whole-chain decision evidence | Shares seven EURIO organisation nodes with CEMCAP; the CEMCAP reporting page also describes CLEANKER as follow-on CaL work. |
| Carbon4Minerals | 101091870 | Capture-to-mineralisation/binder alternative and pilot-feasibility context | Shares two EURIO organisation nodes with CEMCAP; its CORDIS reporting page covers capture, cement, and construction-product pilots. |
| CO2Valorize | 101073547 | Carbonated supplementary-cementitious-material option and research-to-engineering gap | Included for the same cement/CO2 decision, not claimed as an organisation-linked successor. |

The corpus retains five reviewed public documents: the original CEMCAP deliverable and ammonia
publication, plus public CORDIS reporting/results pages for CLEANKER, Carbon4Minerals, and
CO2Valorize. Result metadata remains labelled as metadata. The reporting-page passages are
source-reported claims, not independent proof of performance; the CO2Valorize reduction figure is
explicitly treated as a target/proof-of-concept claim.

## Bounded ingestion and cap

The ingestion command fetches six project records, at most four result-metadata records per
project, and the five public documents above. It archives raw payloads and writes source-version
and evidence catalogs before rebuilding Graphiti/Neo4j evidence episodes. Re-running an unchanged
batch is idempotent. The cap is 10 GB for Neo4j data and indices plus local raw archives and
catalogs.

### Observed live ingestion and source-version probe, 2026-09-24

The initial bounded batch created 21 source versions: 6 project records, 10 result-metadata
records, and 5 retained public documents. A subsequent idempotence probe found that all three
CORDIS HTML reporting/results pages had changed byte-for-byte, so the provenance layer correctly
retained three additional public-document versions rather than treating them as unchanged. The final
live corpus therefore has 24 versions: 6 project, 10 result-metadata, and 8 public-document
versions. Counts below include the untouched frozen group because both live corpora share the local
Neo4j instance.

| Measure | Before | After | Change |
| --- | ---: | ---: | ---: |
| Projects | 3 | 6 | +3 |
| Source versions | 11 | 24 | +13 |
| Full-text/public-document records | 2 | 8 | +6 |
| Neo4j Episodic nodes | 11 | 35 | +24 |
| Neo4j Entity nodes | 33 | 94 | +61 |
| `MENTIONS` relationships | 42 | 144 | +102 |
| `RELATES_TO` relationships | 37 | 116 | +79 |
| Neo4j `/data` + `/logs`, local corpus files | 546,963,098 B | 551,798,249 B | +4,835,151 B |

The final footprint is approximately 552 MB (decimal), leaving approximately 9.448 GB below the
10 GB cap. A previous concurrent local invocation created duplicate derived v2 episodes; it was
removed only from the v2 group and rebuilt from the retained source configuration before these
measurements. The frozen v1 group and its artifacts were not altered. The changing CORDIS HTML
payloads are a source-stability limit: the versions are retained for audit, but a future ingestion
increment should use stable document bytes or canonicalised content if routine polling is required.

Live checks used a cited current CLI investigation (5 EURIO paths, 7 retrieved evidence items,
7.4 s) and the normal HTTP/SSE workbench route (22 projected path edges, 5 evidence items). A
strict 2020 request returned no current EURIO paths and did not use the newly added undated pages;
it answered that no route should be commercially ranked, based only on the two eligible 2018
documents. That is an honest non-ranking, not evidence that no technology exists.

The group ID is `cordis-eurio:cement-industrial-decarbonisation-v2`. It must never be merged with
`cordis-eurio:cement-retrofit-v1`; the frozen evaluation command explicitly selects the latter.

## Interpretation limits

This is not exhaustive CORDIS coverage or a technology ranking dataset. It supports a bounded
shortlisting conversation: identify a route worth site-specific assessment, expose an adjacent
option, and show what evidence is still missing. It cannot establish supplier choice, cost ranking,
commercial readiness, or historical eligibility from current EURIO triples. Newly added CORDIS
pages have no verified publication timestamp in this slice, so strict historical requests must
exclude them rather than infer availability from retrieval time.
