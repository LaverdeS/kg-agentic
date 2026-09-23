# Evaluation method

`evals/cement-retrofit-v1-baseline.json` freezes the bounded CEMCAP, LEILAC2,
and HERCCULES benchmark identity. The command rejects a local corpus whose exact
content-addressed source-version set does not match that manifest. Its question set is in `evals/questions.json`.
Each accepted live report records the complete question configuration, exact persisted
source-version identifiers, model and evidence-limit settings, raw investigation
outputs, failures, latency, and model usage. A later corpus expansion must use a
different corpus identifier; it must not replace this benchmark's source set.

Run the comparison after ingesting the frozen corpus:

```powershell
uv run kg-agentic evaluate --output var/evaluations/cement-retrofit-v1.json
```

The command runs the full agent, an EURIO-only baseline, and a semantic-only
baseline on the same questions and temporal cutoffs. It saves a report even when a
system fails, returns a nonzero status for failures, and never substitutes a
synthetic success. The EURIO-only baseline deliberately abstains because typed
relationships and result metadata are not enough to make a source-supported
recommendation. The semantic-only baseline can use the same source evidence but
does not receive organisation-project-output paths.

The report's automated measures are citation resolvability, a support-based
faithfulness proxy, temporal leakage, reference-identifier coverage, multi-hop
retrieval, expected completion or abstention, latency, model usage, and a six-point
consulting-brief rubric. Citation resolvability and the faithfulness proxy are not
independent proof that source claims are true. The consulting rubric only checks
that the required decision, rationale, alternative, relationship, uncertainty, and
next-action fields are present with retrieved support; independent human review is
explicitly pending.

Software correctness remains in `tests/`; live quality evidence is a separately
saved evaluation artifact. `tests/test_portability.py` also executes the same
evaluator against a synthetic roads-inspection fixture. An adopter supplies a
source adapter that returns the investigation contract, a corpus-qualified task
configuration with reference cases and abstention expectations, and its own review
rubric. This verifies portability of the evaluation seam, not consulting quality in
another domain.
