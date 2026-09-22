# Cement partner and capability validation

This report records deterministic validation for the current, bounded CEMCAP,
LEILAC2, and HERCCULES seed corpus. It is not a claim that a live model or external
review has been completed.

## Decision and evidence boundary

The current question asks which capture pathways and complementary partner candidates
should enter a site-specific retrofit feasibility study. EURIO paths establish only
typed organisation participation and project-to-output links. They do not establish
authorship, supplier status, or a demonstrated capability. The retained CEMCAP D4.5
Zenodo v1 deliverable supports a qualitative technical retrofitability comparison;
it expressly excludes an economic ranking. The retained ammonia publication supports
pilot-test scope, not commercial-scale operation.

The bounded corpus now contains four categories: EURIO project records, EURIO result
metadata, D4.5 public-deliverable full text, and publication full text. Raw versions
are archived and content-addressed by the ingestion pipeline. The deliverable and
publication retain 2018 with year precision, so neither is eligible for an intra-year
historical assertion without a verified public-availability timestamp.

## Deterministic checks

- `tests/test_public_documents.py` proves all four categories are assembled together,
  with retained full-text bytes and conservative publication precision.
- `tests/test_eurio.py` proves original, directed organisation-project-result paths and
  keeps result metadata distinct from text.
- `tests/test_investigation.py` proves that a brief must resolve every material claim
  to retrieved evidence and an invalid citation causes abstention.

The reference questions in `evals/questions.json` cover landscape, capability,
comparables, partners, gaps, and the explicitly unsupported historical request. Each
records an expected path or passage, an abstention condition, and an invalid-citation
case. They are reference cases for the next evaluation ticket, not reported model
quality measurements.

## Current validation action

Do not select a partner on participation alone. Request a current, site-specific
technical response showing the capture boundary, utilities, footprint constraints,
and demonstrated operating evidence. The shortlist changes when that evidence either
substantiates a complementary role under the same boundaries or shows that the role
or comparison does not transfer to the target plant.

## Live validation status

The live EURIO/Graphiti/Neo4j smoke test remains opt-in because it contacts external
services and uses a model. It must be run after ingesting the updated corpus; any
unavailable service is a visible validation blocker rather than a synthetic success.
