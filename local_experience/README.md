# Local evidence explorer

This optional workspace is a removable entry-point slice: the browser receives a
vendor-neutral scene projection from the existing investigation result. It has no
path back into `src/kg_agentic/`, and it never receives Neo4j credentials or
vendor query access.

## Run the recorded walkthrough

```powershell
npm run ui:build
.\.venv\Scripts\python.exe -m local_experience.api.server
```

Open `http://127.0.0.1:8000`. The first view is explicitly a deterministic,
current-only recorded snapshot of the cement slice, for inspecting interaction
and citation behavior without an API call. Editing its question changes the run
context only; it does not claim to generate a new answer.

On a first visit, the optional **Quick guide** introduces the intended two-minute
journey: start a recorded question, follow the public activity, inspect the
amber CEMCAP D4.5 citation, then ask a follow-up. It can be dismissed and
reopened from **Guide** in the header. Questions about the app's purpose,
capabilities, connected data, or sources receive an honest orientation response
without invoking retrieval or changing the graph; ask a consulting question to
start a bounded investigation.

`POST /api/conversations` accepts a `threadId`, question, mode, optional
`selectedNodeIds`, and (for live mode only) an ISO `asOf` cutoff. It runs a
small LangGraph workflow with process-local, thread-scoped checkpoints, calls
the existing investigation composition, and sends only bounded public SSE
stages: `planned`, `retrieved_path`, `evidence_found`, and `claim_supported`.
`DELETE /api/conversations/<threadId>` clears that local thread. Restarting the
server also clears every thread. Selection is navigation context, never
evidence; live historical questions still enforce the core's strict
cutoff-eligibility policy. If EURIO, Neo4j, or the model is unavailable, the
route sends a failure event instead of substituting the recorded snapshot.

The recorded scene now includes the source-qualified CEMCAP D4.5 full-text
deliverable as distinct from project records, metadata-only results, and the
ammonia publication. It remains a current-only UI fixture: it cannot answer a
historical question or claim a newly generated recommendation.

## Renderer decision

The initial renderer is Sigma.js 3 + Graphology: it is MIT-licensed, WebGL-first,
and keeps the scene contract independent from the renderer. Sigma has the right
performance and visual-control profile for a small constellation-like working
subgraph, while a synchronized DOM scene index and inspector supply keyboard and
non-canvas access.

The decision remains deliberately reversible. Cytoscape.js offers a stronger
headless/layout ecosystem; Neo4j Visualization Library offers especially direct
Neo4j-style incremental graph APIs but needs a licence and telemetry review;
react-force-graph is a good future 3D comparison candidate but its animated
force layout is a weaker default for stable investigation scenes. Sources:
[Sigma](https://www.sigmajs.org/), [Cytoscape](https://js.cytoscape.org/),
[NVL](https://neo4j.com/docs/nvl/current/), and
[react-force-graph](https://github.com/vasturiano/react-force-graph).

## Browser check

After building the client and starting the local server, run the deterministic
recorded journey with:

```powershell
npm run ui:test
```

It checks the conversation/public-activity flow, CEMCAP D4.5 inspection,
reduced-motion preference, first-use guide, intent-aware capability response,
and the keyboard-accessible evidence/detail surface.
