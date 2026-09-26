# AI Knowledge & Agent Architecture: Decision Guide

**Use on a client call:** frame the need → choose a table row → agree the first build and acceptance criteria.

*Canonical consulting reference · Sources checked 26 September 2026 · Recommendations require client-specific evaluation.*

## Frame the decision first

**Outcome:** user, decision/action, benefit, owner. **Evidence:** example questions, authoritative sources, access and quality. **Time:** current versus historical answers, update frequency. **Boundaries:** permissions, privacy, residency, retention, approvals. **Economics:** volume, response time, budget, existing platforms and operating skills. Record unknowns; do not invent requirements.

## 30-second triage

**Existing software, rules or SQL suffice?** Use them; a language model (LLM) is optional. **Need explanations from evidence?** Retrieve, then generate (RAG). **Need connected facts?** Test joins/traversal. **Need history?** Test versioned records first. **Need shared meaning?** Govern definitions. **Need adaptive execution?** Test an agent. These are independent choices, not a maturity ladder.

## Start here; grow only when justified

| Business case | Start here | Grow when justified | Avoid |
|---|---|---|---|
| Small, stable handbook | Full context; optional caching ([CAG](https://arxiv.org/abs/2412.15605), [code](https://github.com/hhhuang/CAG)) | Retrieval for quality, size, freshness or permission needs | Assuming “fits” means reliable |
| Policies, contracts, manuals | RAG; compare keyword and hybrid search | Fix parsing/chunks; then rerank or rewrite queries | Graphs merely for entity mentions |
| ERP/CRM status, figures, totals | Authorized SQL/API queries | RAG for explanations | Vector matches as current truth or complete counts |
| Dependencies, ownership, shared directors | SQL joins; graph for complex paths | GraphRAG: answers grounded in graph evidence | Unverified extracted relationships |
| Preferences, project state, changing facts | Profile/state records; versions/history | Temporal graph memory for relationship/history retrieval | Graphiti merely because data changes |
| Shared business definitions | Vocabulary + source mappings | RDF for interoperability; validation/inference as needed | Assuming regulation requires RDF |
| Themes across reports | Hierarchical summaries | Compare [Microsoft GraphRAG](https://microsoft.github.io/graphrag/query/global_search/) community reports ([code](https://github.com/microsoft/graphrag)) | Ignoring coverage/update cost |
| Actions, multiple tools, variable steps | Fixed workflow | Agent when the model must adapt its next steps | Agency for every API call or write |

## Graph-language fast selector

| Need | Choose | Boundary |
|---|---|---|
| Application paths/dependencies | Property graph: nodes, relationships, properties; [Cypher](https://neo4j.com/docs/cypher-manual/current/introduction/) for Neo4j | Cypher ≠ GQL; check [conformance](https://neo4j.com/docs/cypher-manual/current/appendix/gql-conformance/) |
| Shared identifiers and formal semantics | [RDF](https://www.w3.org/TR/rdf11-primer/) triples + [SPARQL](https://www.w3.org/TR/sparql11-overview/) queries | [SHACL](https://www.w3.org/TR/shacl/) validates constraints; [OWL](https://www.w3.org/TR/owl2-overview/) enables formal inference; neither is mandatory |
| Platform-specific traversal | [Gremlin](https://tinkerpop.apache.org/gremlin.html) where required | Follow platform capabilities ([Neptune comparison](https://docs.aws.amazon.com/neptune/latest/userguide/get-started-access-graph.html)) |
| Temporal graph memory | [Graphiti](https://github.com/getzep/graphiti) → extraction, temporal facts, provenance, hybrid retrieval → Neo4j/FalkorDB | Framework above a database, not a query language ([quickstart](https://help.getzep.com/graphiti/getting-started/quick-start)) |

**Hybrid search** combines keywords and vector similarity (meaning). An **ontology** defines concepts/relationships for either graph model; both support GraphRAG. For memory, separate **valid time** from **when learned**, and documents from mutable context; define authority, conflicts, scope and expiry.

## Agentic AI: add agency only when justified

Start with `question → retrieve/query → answer`, or a fixed action workflow. Use an agent for adaptive tool selection, planning or iteration; bound tools, steps, time, cost and escalation. Multiple agents need measurable benefit from separable work. [Agent/workflow patterns](https://www.anthropic.com/engineering/building-effective-agents); [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) for resumable orchestration, not knowledge storage.

## Grow a property graph: extract → enhance → expand

**Example: connect filing risks to reported investment positions**, adapting the [source diagram](<extract enhance and expand.png>).

1. **Extract:** 10-K → filing/chunk nodes; structured 13F records → manager, position, security and issuer nodes. Preserve source passages; validate prose extraction.
2. **Enhance:** stable IDs, uniqueness constraints, verified entity/alias mappings, chunk embeddings, full-text indexes; retain source/version, dates and units.
3. **Expand:** `Chunk → PART_OF → Filing ← FILED ← Company`; `Manager → FILED → 13F → REPORTS → Position → IN_SECURITY → Security → ISSUED_BY → Company`. Add chunk adjacency, risks/people/places and sourced relationships only for useful questions; keep user feedback separate.

Retrieve passages, traverse authorized paths, filter reporting/as-of dates and amendments, then cite evidence. Use [SEC/XBRL APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) for structured financial facts.

> **Watch your claims:** mention ≠ causality; inference ≠ verified truth; top-k retrieval ≠ complete coverage. [13F](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f) reports investment discretion, not necessarily beneficial ownership or current holdings. A [CUSIP](https://www.cusip.com/identifiers.html) issuer prefix is not a universal company key. Preserve evidence, identity and time qualifiers.

## First build, evaluation and warning signs

**Build:** one user journey, thin service (e.g. FastAPI), minimal models/stores, citations and traces. Agree expert-reviewed cases and pass/fail thresholds; **30–100 cases** is a starting heuristic, not proof. Include unseen, missing, conflicting, stale and unauthorized cases.

**Measure:** business/task success, evidence retrieval, answer/citation correctness, abstention, entity/link accuracy, action safety, tail latency and total cost. Fix parsing before retrieval tuning; test graphs against SQL/RAG and agents against fixed workflows. Change one capability, re-evaluate, stop when targets are met.

**Simplify when:** components lack a business question; duplication lacks ownership; agents replace predictable code; memory lacks provenance/retention; ingestion cannot replay; debugging is opaque; no evaluation shows benefit. Split stores or add event-driven ingestion only for measured bottlenecks.

## Production gates

- **Access:** enforce user/tenant permissions through retrieval, graph expansion, memory, summaries, caches and tools.
- **Actions:** treat retrieved content as untrusted; authorize outside the model; validate arguments/queries, prefer constrained read-only templates; approve consequential writes; make retries safe. [OWASP controls](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- **Data:** versioned, duplicate-safe ingestion; propagate corrections/deletions; assign schema, source and memory owners; define retention.
- **Operations:** pin models/embeddings/prompts/dependencies; plan reindexing, tested restores, rollback and fallback; protect traces; monitor quality, freshness, errors, latency and cost. Pass regression/security checks before access.

## Fast stack defaults and implementation references

Reuse existing capabilities; compare managed alternatives, licenses, residency and operating cost. These are candidates, not a mandatory bundle.

| Capability | Starting point |
|---|---|
| Retrieval | Existing Postgres: [pgvector + full-text](https://github.com/pgvector/pgvector); dedicated: [Qdrant hybrid](https://qdrant.tech/documentation/search/hybrid-queries/) |
| Property graph | [Neo4j retrieval](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html); [KG builder](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html) is experimental |
| Separate vector/graph scaling | [Qdrant + Neo4j integration](https://qdrant.tech/documentation/frameworks/neo4j-graphrag/), [worked example](https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/); own synchronization/deletion |
| RDF store / local models / GPU serving / observability | [Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) / [Ollama](https://docs.ollama.com/) / [vLLM](https://docs.vllm.ai/en/latest/serving/online_serving/) / [Langfuse](https://langfuse.com/self-hosting) |

## Bootstrap handoff

- **Brief:** outcome/owner, questions, sources/access/freshness, constraints and unknowns.
- **Design:** minimal architecture, rejected alternatives, ingestion/schema/query/tool plan.
- **Proof and delivery:** evaluation cases/thresholds, deployment, cost and operating owner.
- **Next steps:** build sequence, unresolved assumptions and measurable expansion triggers.
