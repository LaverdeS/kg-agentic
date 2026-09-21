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

`POST /api/investigations` also accepts `{"mode": "live", "question": "..."}`.
That route invokes the existing application composition. If EURIO, Neo4j, or the
model is unavailable, it sends a failure event instead of substituting the
recorded snapshot.

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
