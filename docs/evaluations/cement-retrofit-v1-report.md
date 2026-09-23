# Cement retrofit v1 evaluation report

## Execution status — 2026-09-23

No live comparison result is recorded yet. The `kg-agentic evaluate` command was
implemented and deterministic checks passed, but this session was not authorized to
send the retained local corpus to EURIO, Neo4j/Graphiti, and the configured model
provider. Consequently there are no observed retrieval, citation, latency, model-use,
or consulting-quality scores, and this document makes no claim that the full agent
outperforms either baseline.

The blocking validation is:

```powershell
uv run kg-agentic evaluate --output var/evaluations/cement-retrofit-v1.json
```

Run it only with the intended local Neo4j graph, EURIO access, and model credentials.
The command rejects any source-version set that differs from the committed frozen
baseline, saves raw current and historical outputs for all systems, and returns
nonzero if any system fails. Review the saved report against the method and record
whether the observed comparison supports, weakens, or leaves unresolved the proposed
agent advantage.

## Deterministic evidence

The shared evaluator is covered by `tests/test_evaluation.py`; the synthetic
roads-inspection fixture runs through the same evaluation seam in
`tests/test_portability.py`. These checks validate report construction, citation
resolution, temporal eligibility, failure capture, and portability. They are not a
substitute for the required live comparison.
