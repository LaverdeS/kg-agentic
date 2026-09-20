# GraphRAG for evidence-led consulting

Turn connected research evidence into consulting recommendations that can be explained, challenged, and acted on.

The concept combines an investigating agent with a knowledge graph and dated source evidence. Its purpose is to help consultants discover useful relationships, assess what the evidence supports, and turn those findings into better decisions.

## The business case

Technology and innovation consulting requires more than finding relevant documents. A useful recommendation connects organizations to projects, projects to outputs, and those outputs to demonstrated capabilities. It also explains how strong the evidence is and whether new findings change the decision.

The intended value is faster evidence gathering, more informed partner and technology choices, and a clear basis for client review. A recommendation should make its rationale, alternatives, uncertainties, and next validation steps visible.

| Consulting decision | Insight to pursue |
| --- | --- |
| Technology landscape | Where activity is concentrated, which approaches are emerging, and which have demonstrated results. |
| Capability assessment | What an organization has evidence of delivering, and where its claims still need validation. |
| Comparable-project analysis | Which projects offer relevant precedents based on their relationships, methods, and outcomes. |
| Partner discovery | Which organizations bring complementary capabilities, supported by their work and collaboration history. |
| Gap detection | Where the available evidence leaves an important decision unanswered. |
| Change monitoring | Which newly available findings strengthen, weaken, or change a recommendation. |

## The distinctive idea

The agent is designed to plan an investigation, follow relationships across sources, retrieve relevant evidence, and check whether that evidence is sufficient for a recommendation. The result is a cited brief that connects findings to a concrete consulting decision.

The proposed advantage lies in combining relationship reasoning with evolving evidence: uncovering a useful connection across projects, explaining why it matters, and tracing the recommendation back to its support. Success means more useful and defensible insights than simpler search or retrieval can provide.

## CORDIS as the first application

The official [CORDIS EURIO Knowledge Graph](https://cordis.europa.eu/about/sparql) provides the canonical semantic foundation for the first application: projects, organizations, research outputs, and their relationships. CORDIS project records, results, public deliverables, and publications provide the supporting evidence.

EURIO already supplies the knowledge graph. This project adds an investigation and recommendation layer over that foundation. Graphiti with Neo4j is the selected initial backend for dated evidence memory.

The first niche is cement carbon-capture retrofit diligence: helping a producer's engineering team shortlist capture approaches and complementary partners for a site-specific feasibility study. The initial evidence scope connects CEMCAP, LEILAC2, and HERCCULES. The intended brief will distinguish tested results from planned demonstrations and make differences in capture boundaries, utility requirements, and cost assumptions explicit.

## Current vertical slice

The repository now contains a bounded end-to-end investigation path for that niche. It queries
live EURIO relationships, ingests source-qualified CORDIS project/result records plus one
versioned public publication into Graphiti on
Neo4j, retrieves both structural paths and semantic evidence, and asks an OpenAI model for a
structured brief. A support gate removes every material generated claim that cannot be resolved to
retrieved evidence with an HTTP citation. If paths, evidence, or supported claims are missing, the
agent abstains instead of manufacturing an answer.

This is deliberately a current-evidence slice. Historical `--as-of` requests are rejected before
retrieval because reliable publication-time eligibility is not yet available for all selected
CORDIS records. The seed corpus is also intentionally small: three project records and at most two
result records per project for CEMCAP (`641185`), LEILAC2 (`884170`), and HERCCULES (`101096691`),
plus a reviewed passage from one public CEMCAP-linked publication. Result metadata remains
distinct from full-text evidence; the currently unavailable CEMCAP D4.5 deliverable is not ingested.

## Run locally

Prerequisites are Python 3.12 or 3.13, [uv](https://docs.astral.sh/uv/), Docker Desktop, an OpenAI
API key with available API credit, and network access to the public EURIO SPARQL endpoint.

```powershell
uv sync --extra dev
Copy-Item .env.example .env
```

Fill `OPENAI_API_KEY` and `NEO4J_PASSWORD` in the ignored `.env` file yourself. Do not commit that
file. The remaining settings have runnable local defaults; `.env.example` documents the model,
embedding, concurrency, evidence-limit, and data-directory overrides.

Start Neo4j, ingest the bounded corpus once, and run the current investigation:

```powershell
docker compose up -d neo4j
uv run kg-agentic ingest
uv run kg-agentic investigate
```

Ingestion stores versioned raw source payloads under the ignored `var/corpora/` directory and skips
unchanged source versions on subsequent runs. Both commands contact real services and fail visibly
when EURIO, Neo4j, or OpenAI is unavailable; there is no synthetic production fallback.

Useful checks and alternate output are:

```powershell
uv run kg-agentic investigate --json
uv run kg-agentic investigate --as-of 2025-01-01
uv run kg-agentic evaluate
uv run pytest
uv run ruff check .
uv run pyright
```

The historical command exits non-zero with an explicit unsupported status. The live integration
test is opt-in because it incurs API calls:

```powershell
$env:RUN_LIVE = "1"
uv run pytest tests/test_live_stack.py -q
```

## Recommendations that can be audited

A brief should distinguish source-backed facts, source-reported claims, model extractions, and agent hypotheses. Each supported claim should lead back to an identifiable source and the relevant passage or relationship.

Dates matter: when something happened, when its evidence became public, and when it was ingested answer different questions. Historical recommendations should rely on evidence demonstrably available at the requested time. Missing or conflicting support should narrow the conclusion and guide further investigation.

This discipline makes uncertainty actionable. Participation in a project alone does not establish a capability; a missing public record alone does not establish its absence.

## A foundation for other datasets

Delivering consulting value from CORDIS is the primary goal. A secondary goal is a reusable template for agentic GraphRAG work with other datasets and niches.

The design separates the investigation process and evidence-handling rules from source-specific mappings and consulting questions. Future applications should be able to retain the same approach to provenance, temporal reasoning, citations, and evaluation while adapting their data connections, domain relationships, and decision criteria.

CORDIS provides a concrete setting in which to demonstrate the approach and assess its value.
