# Cement retrofit v1 evaluation report

## Execution status — 2026-09-23

The frozen live comparison completed without system failures. Its full raw report is
saved locally at `var/evaluations/cement-retrofit-v1.json`; it records the committed
11 content-addressed source versions, full question configuration, raw current and
historical outputs, run-level scores, latency, and model use. A PostHog telemetry
upload reported a TLS error during the command, but EURIO, local Neo4j/Graphiti, and
the model-backed evaluation runs completed.

| System | Completed | Abstained | Failed | Mean latency | Model tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full agent | 7 | 1 | 0 | 8.9 s | 27,314 |
| EURIO-only | 0 | 8 | 0 | 0.2 s | 0 |
| Semantic-only | 6 | 2 | 0 | 7.4 s | 21,777 |

The full agent matched every configured expected completion/abstention outcome,
including a correct abstention at the unsupported `2018-12-31` cutoff; no temporal
leakage was observed. Its automated citation-resolvability and faithfulness proxies
were 0.875, versus 0.75 for semantic-only. The full agent's consulting-brief proxy
was 5.0/6, versus 3.75/6 for semantic-only, and it completed the cross-project partner
case that semantic-only abstained on. EURIO-only correctly avoids making a cited
recommendation from paths and metadata alone, so it abstained throughout.

This narrowly supports the proposed advantage for the frozen corpus: structural paths
appear to add value to semantic evidence for the partner/comparison workflow. It does
not establish general consulting superiority: expected-support coverage was only
0.1875 for both evidence-bearing systems, the scores are automated proxies, and no
independent human consulting review was performed. The two historical change runs
retrieved the same two dated full-text versions at both cutoffs; no later-only evidence
was observed, and the result does not claim a real-world technology change.

Reproduce the report with:

```powershell
uv run kg-agentic evaluate --output var/evaluations/cement-retrofit-v1.json
```

Run it only with the intended local Neo4j graph, EURIO access, and model credentials.
The command rejects any source-version set that differs from the committed frozen
baseline, saves raw current and historical outputs for all systems, and returns
nonzero if any system fails.

## Deterministic evidence

The shared evaluator is covered by `tests/test_evaluation.py`; the synthetic
roads-inspection fixture runs through the same evaluation seam in
`tests/test_portability.py`. These checks validate report construction, citation
resolution, temporal eligibility, failure capture, and portability. They do not
replace the bounded live result above or an independent human review.
