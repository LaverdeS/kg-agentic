# Local evidence explorer

This optional browser workspace is a live entry point to the existing
investigation composition. It never serves a saved graph, a recorded brief, or
a replayed source list. The first screen is intentionally empty: a graph,
retrieved evidence, and a structured brief appear only when a new live run
returns them.

## Run it

```powershell
npm run ui:build
.\.venv\Scripts\python.exe -m local_experience.api.server
```

Open `http://127.0.0.1:8000`. Set `OPENAI_API_KEY`, `NEO4J_PASSWORD`, and the
other usual core settings before asking an investigation question. If EURIO,
Neo4j, or the model is unavailable, the explorer reports that real failure; it
does not substitute demo data.

## What the agent does

The local LangGraph wrapper has three explicitly bound actions:

1. `check_live_services` checks the current local configuration.
2. `recommend_test_tasks` offers six varied questions for exercising the app.
3. `investigate_live_graph` invokes the core investigation path afresh and
   projects only its returned paths, evidence, gaps, and supported brief.

The wrapper retains only the short chat thread. A selected graph item can guide
the next question, but it is not evidence and is never reused as a result. Each
decision question executes `investigate_live_graph` again. The core remains the
authority for retrieval and the supported recommendation, so the explorer does
not add a second unconstrained answer generator.

Its operating instruction reflects the product’s purpose: turn European
research relationships and dated public sources into inspectable decisions;
separate structural links from source claims; state uncertainty; and never
treat participation, objectives, or absence of data as proof.

`POST /api/conversations` accepts `threadId`, `question`, optional
`selectedNodeIds`, and an optional ISO `asOf` cutoff. It emits bounded public
SSE stages and a `completed` scene. `GET /api/health` reports `live-only` and
the current tool count. `DELETE /api/conversations/<threadId>` clears local
chat history. All responses use `Cache-Control: no-store`.

## Suggested live tests

- Compare CEMCAP and LEILAC2 for a retrofit decision; name unsafe assumptions.
- Find evidence that would support or rule out an oxyfuel retrofit pathway.
- Identify partners worth validating for complementary capture work.
- Surface the decision-critical gap in a cement retrofit shortlist.
- Ask what the returned public sources establish versus what remains unverified.
- Repeat a question with a strict historical date and inspect abstention or gaps.

## Renderer decision

The renderer is Sigma.js 3 + Graphology: it is MIT-licensed, WebGL-first, and
keeps the scene contract separate from the renderer. A synchronized DOM index
and inspector provide keyboard access to the returned graph and evidence.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_experience.py -q
npm run ui:build
```
