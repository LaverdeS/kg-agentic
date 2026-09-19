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

## Recommendations that can be audited

A brief should distinguish source-backed facts, source-reported claims, model extractions, and agent hypotheses. Each supported claim should lead back to an identifiable source and the relevant passage or relationship.

Dates matter: when something happened, when its evidence became public, and when it was ingested answer different questions. Historical recommendations should rely on evidence demonstrably available at the requested time. Missing or conflicting support should narrow the conclusion and guide further investigation.

This discipline makes uncertainty actionable. Participation in a project alone does not establish a capability; a missing public record alone does not establish its absence.

## A foundation for other datasets

Delivering consulting value from CORDIS is the primary goal. A secondary goal is a reusable template for agentic GraphRAG work with other datasets and niches.

The design separates the investigation process and evidence-handling rules from source-specific mappings and consulting questions. Future applications should be able to retain the same approach to provenance, temporal reasoning, citations, and evaluation while adapting their data connections, domain relationships, and decision criteria.

CORDIS provides a concrete setting in which to demonstrate the approach and assess its value.
