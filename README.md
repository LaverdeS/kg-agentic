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
live EURIO relationships, ingests source-qualified CORDIS project/result records plus reviewed,
versioned public deliverable and publication text into Graphiti on
Neo4j, retrieves both structural paths and semantic evidence, and asks an OpenAI model for a
structured brief. A support gate removes every material generated claim that cannot be resolved to
retrieved evidence with an HTTP citation. If paths, evidence, or supported claims are missing, the
agent abstains instead of manufacturing an answer.

The slice supports strict historical cutoffs as well as current investigation. A historical brief
admits only source versions demonstrably public by its cutoff; event, retrieval, ingestion, and
Graphiti timestamps are not substitutes for public availability. Historical retrieval uses a
durable source-version catalog rather than querying the current Graphiti graph, so later graph
state cannot rank or expand its evidence. The live EURIO endpoint does not currently expose dated
source versions for its relationship triples, so historical briefs omit those paths rather than
presenting current relationships as past knowledge. A resulting source-only brief says so
explicitly. The seed corpus is intentionally small: three project
records and at most two result records per project for CEMCAP (`641185`), LEILAC2 (`884170`), and
HERCCULES (`101096691`), plus reviewed passages from a versioned public CEMCAP D4.5 deliverable
and a CEMCAP-linked publication. This demonstrates all four source categories while retaining
result metadata as distinct from full-text evidence. D4.5 supports a technical retrofitability
comparison, not an economic ranking or supplier qualification; project participation likewise
identifies candidates for validation rather than proved capabilities.

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

Start Neo4j, ingest the bounded corpus once, and run an investigation:

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
uv run kg-agentic investigate --as-of 2019-01-01
uv run kg-agentic compare --from 2019-01-01 --to 2020-01-01
uv run kg-agentic evaluate
uv run pytest
uv run ruff check .
uv run pyright
```

## Explore the evidence locally

The optional local explorer presents the current cement slice as a 2D evidence
constellation beside its cited brief. It is separate from the core investigation
package and starts with a clearly labelled recorded, current-only snapshot so
the experience can be inspected without consuming model credit:

> This tool helps a cement producer explore which carbon-capture approaches and
> partners are worth taking into a site-specific feasibility study. Ask a
> question, and it connects relevant EU research projects, the organisations
> involved, their documented outputs, and the underlying public evidence. You
> can follow each suggested next step back to its source and see where evidence
> is strong, uncertain, or still missing before committing engineering time or
> capital.

```powershell
npm install
npm run ui:build
.\.venv\Scripts\python.exe -m local_experience.api.server
```

Open `http://127.0.0.1:8000`. Select a graph element, cited evidence link, or
keyboard-accessible scene-index item to inspect its identifiers and provenance.
The explorer's editable recorded walkthrough changes its run context only; it
does not present a synthetic fresh recommendation. Its live API route invokes
the same core use case as the CLI and reports unavailable services explicitly.

The comparison command reports source-qualified evidence versions retrieved only at one cutoff;
it explicitly does not treat a retrieval/ranking difference as newly eligible evidence or a
real-world change. Year-only publication dates are eligible only after that calendar year has
ended; unknown dates never support a strict historical claim. The live integration test is opt-in
because it incurs API calls:

```powershell
$env:RUN_LIVE = "1"
uv run pytest tests/test_live_stack.py -q
```

## Recommendations that can be audited

A brief should distinguish source-backed facts, source-reported claims, model extractions, and agent hypotheses. Each supported claim should lead back to an identifiable source and the relevant passage or relationship.

Dates matter: when something happened, when its evidence became public, and when it was ingested
answer different questions. Historical recommendations rely only on evidence demonstrably
available at the requested time, and the citation gate repeats that check after generation.
Changed source versions remain separate, traceable evidence rather than overwriting their earlier
versions. Missing or conflicting support narrows the conclusion and guides further investigation.

This discipline makes uncertainty actionable. Participation in a project alone does not establish a capability; a missing public record alone does not establish its absence.

## A foundation for other datasets

Delivering consulting value from CORDIS is the primary goal. A secondary goal is a reusable template for agentic GraphRAG work with other datasets and niches.

The design separates the investigation process and evidence-handling rules from source-specific mappings and consulting questions. Future applications should be able to retain the same approach to provenance, temporal reasoning, citations, and evaluation while adapting their data connections, domain relationships, and decision criteria.

CORDIS provides a concrete setting in which to demonstrate the approach and assess its value.
