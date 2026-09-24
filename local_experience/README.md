# Local Evidence Workbench

This optional browser workspace lets you talk with Mira, investigate connected
public research, and inspect the sources behind a decision. It calls the live
EURIO and local Graphiti/Neo4j investigation path. The running product has no
recorded or synthetic answer mode.

## Run locally

From the repository root, with Neo4j running and the environment configured:

```powershell
npm install
npm run ui:build
.\.venv\Scripts\python.exe -m local_experience.api.server
```

Open `http://127.0.0.1:8000`. See the root README for ingestion and credentials.
The API listens on localhost only. It reports model or dependency failures in
the conversation instead of replacing them with a demo answer.

## What Mira can do

- Talk naturally, explain terms, and help frame a useful research question.
- Inspect the current source-version manifest and the graph built in this
  conversation. Counts are read when requested, not memorised in the prompt.
- Focus an element already visible in the map.
- Run one bounded evidence investigation over the configured corpus. The core
  support gate controls the cited brief, and the answer names uncertainty and
  a next validation step.

The two read-only research tools are `inspect_workspace` and
`investigate_live_graph`. General chat and navigation do not create evidence.
The map grows across evidence questions in one thread, while each answer and
its citations refer to that question's retrieval. A different historical
cutoff starts a separate map. Reset thread clears the chat and map. All memory
is local to the running process.

During investigation, the stream reports relationship retrieval and source
retrieval as they complete. The map shows those partial results before the
brief finishes. Newly returned elements receive a short highlight. The Trace
tab contains public activity only; it does not reveal private model reasoning.
Search, neighboring links, fit/zoom, filters, and a non-canvas Sources view
support exploration. Selection guides a follow-up but is never evidence.

## Try it

1. Ask `How many project and source records are indexed right now?` to test
   the live inspection tool. This should leave the map empty.
2. Ask `Using the indexed public sources, what evidence should guide a cement
   retrofit feasibility study?` Watch the graph appear during the run.
3. Search for a project or source in the map, follow a linked element, then
   choose **Ask about this** for a follow-up.
4. Open a citation, compare the source detail with the claim, and inspect
   **Trace**. Try a historical cutoff and observe its separate map.

The corpus is a bounded cement-decarbonisation selection. Project and result
metadata is distinct from retained public text. Current graph links do not
automatically become historical facts, and a source gap does not establish
real-world absence.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_experience.py -q
npm run ui:build
npm run ui:test
```

The browser tests use controlled SSE responses. Check the real stack separately
because it uses network services and model credit.
