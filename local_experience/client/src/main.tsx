import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { getHealth, resetConversation, streamConversation } from "./api";
import type { Citation, ConversationMessage, Scene, SceneEdge, SceneNode, Statement, Trace } from "./types";
import "./style.css";

const allKinds = ["project", "organization", "role", "output", "evidence", "entity"];
const guidedQuestion = "Which CEMCAP evidence should I inspect first for a retrofit decision?";
const emptyScene: Scene = {
  question: "",
  status: "ready",
  mode: "live",
  nodes: [],
  edges: [],
  evidence: [],
  brief: null,
  trace: [],
  gaps: [],
};
const starterPrompts = [
  { label: "Explain retrofit", question: "What is retrofit in this context?" },
  { label: "What is indexed?", question: "How many project and source records are indexed right now?" },
  { label: "Compare projects", question: "Compare the available CEMCAP and LEILAC2 evidence for a retrofit feasibility study." },
  { label: "Decision gap", question: "What evidence gap matters most before choosing a cement retrofit pathway?" },
];
const activityTitles: Record<string, string> = {
  interpreting: "Reading your question",
  planned: "Planning the research",
  retrieved_path: "Connected research paths",
  evidence_found: "Found public sources",
  claim_supported: "Checked the answer",
  inspected: "Read current workspace facts",
  answered: "Answered without research tools",
  focused: "Focused the current map",
};
type ResearchView = "graph" | "sources" | "trace";
const GraphCanvas = lazy(() => import("./GraphCanvas").then((module) => ({
  default: module.GraphCanvas,
})));

function mergeGraph(current: Scene, next: Pick<Scene, "nodes" | "edges">): Pick<Scene, "nodes" | "edges"> {
  const nodes = new Map(current.nodes.map((node) => [node.id, node]));
  const edges = new Map(current.edges.map((edge) => [edge.id, edge]));
  next.nodes.forEach((node) => nodes.set(node.id, node));
  next.edges.forEach((edge) => edges.set(edge.id, edge));
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

function App() {
  const [scene, setScene] = useState<Scene>(emptyScene);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>(null);
  const [visibleKinds, setVisibleKinds] = useState(new Set(allKinds));
  const [visibleRelationshipTypes, setVisibleRelationshipTypes] = useState(new Set<string>());
  const [search, setSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [toolCount, setToolCount] = useState<number | null>(null);
  const [coverage, setCoverage] = useState({ projectRecords: 0, resultMetadataRecords: 0, fullTextRecords: 0, sourceVersions: 0 });
  const [activities, setActivities] = useState<Trace[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "running" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);
  const [guideOpen, setGuideOpen] = useState(false);
  const [researchView, setResearchView] = useState<ResearchView>("graph");
  const [mapRuns, setMapRuns] = useState(0);
  const [latestNodeIds, setLatestNodeIds] = useState(new Set<string>());
  const [activeNodeIds, setActiveNodeIds] = useState(new Set<string>());
  const [viewCommand, setViewCommand] = useState<{ action: "fit" | "in" | "out"; token: number }>({ action: "fit", token: 0 });
  const mapCutoff = useRef<string | null>(null);
  const activityTimer = useRef<number | null>(null);
  const threadId = useRef(crypto.randomUUID());
  const guideButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    getHealth()
      .then((health) => {
        setToolCount(health.toolCount);
        setCoverage(health.coverage);
        setState("ready");
      })
      .catch((nextError: Error) => {
        setError(nextError.message);
        setState("failed");
      });
  }, []);

  useEffect(() => () => { if (activityTimer.current !== null) window.clearTimeout(activityTimer.current); }, []);

  const selected = useMemo(
    () => scene.nodes.find((node) => node.id === selectedId) ?? null,
    [scene.nodes, selectedId],
  );
  const relationshipTypes = useMemo(
    () => [...new Set(scene.edges.map((edge) => edge.label))].sort(),
    [scene.edges],
  );
  const searchMatches = useMemo(
    () => search.trim()
      ? scene.nodes.filter((node) => `${node.label} ${node.id}`.toLowerCase().includes(search.toLowerCase()))
      : [],
    [scene.nodes, search],
  );
  const indexNodes = search.trim() ? searchMatches : scene.nodes;
  const selectedConnections = selectedId
    ? scene.edges.filter((edge) => edge.source === selectedId || edge.target === selectedId)
    : [];
  const messages = scene.conversation?.messages ?? [];
  const runningLabel = activityTitles[activities.at(-1)?.action ?? ""] ?? "Mira is working";
  const hasStructuredResult = scene.conversation?.intent === "investigation";
  const highlightedNodeIds = useMemo(() => {
    const highlighted = new Set<string>();
    if (!hasStructuredResult || !scene.brief) return highlighted;
    const statements = [
      scene.brief.decision,
      scene.brief.recommendation,
      scene.brief.uncertainty,
      scene.brief.next_action,
      ...scene.brief.alternatives,
      ...scene.brief.claims,
    ];
    for (const statement of statements) {
      for (const citation of statement.citations) highlighted.add(`evidence:${citation.evidence_id}`);
    }
    for (const edge of scene.edges) {
      if (highlighted.has(edge.source)) highlighted.add(edge.target);
      if (highlighted.has(edge.target)) highlighted.add(edge.source);
    }
    return highlighted;
  }, [hasStructuredResult, scene]);

  const select = useCallback((id: string, nextView?: ResearchView) => {
    setSelectedId(id);
    if (nextView) setResearchView(nextView);
    requestAnimationFrame(() => document.getElementById("details")?.focus());
  }, []);
  const resetScene = () => {
    setSelectedId(null);
    setPinnedId(null);
    setVisibleKinds(new Set(allKinds));
    setVisibleRelationshipTypes(new Set(relationshipTypes));
    setSearch("");
    setViewCommand((current) => ({ action: "fit", token: current.token + 1 }));
  };
  const toggle = (value: string, update: React.Dispatch<React.SetStateAction<Set<string>>>) => {
    update((current) => {
      const next = new Set(current);
      next.has(value) ? next.delete(value) : next.add(value);
      return next;
    });
  };
  const run = async (requestedQuestion = question, contextId = selectedId) => {
    if (!requestedQuestion.trim()) return;
    const nextCutoff = asOf || null;
    const sameCutoff = mapRuns > 0 && mapCutoff.current === nextCutoff;
    let sawGraphDelta = false;
    setState("running");
    setError(null);
    setActivities([]);
    setActiveNodeIds(new Set());
    try {
      const nextScene = await streamConversation(
        {
          question: requestedQuestion,
          threadId: threadId.current,
          selectedNodeIds: contextId ? [contextId] : [],
          asOf: asOf || null,
        },
        (trace) => {
          setActivities((current) => [...current, trace]);
          if (trace.action === "claim_supported" && trace.nodeIds?.length) {
            setActiveNodeIds(new Set(trace.nodeIds));
            if (activityTimer.current !== null) window.clearTimeout(activityTimer.current);
            activityTimer.current = window.setTimeout(() => setActiveNodeIds(new Set()), 2200);
          }
        },
        (delta) => {
          sawGraphDelta = true;
          setActiveNodeIds(new Set(delta.nodes.map((node) => node.id)));
          if (activityTimer.current !== null) window.clearTimeout(activityTimer.current);
          activityTimer.current = window.setTimeout(() => setActiveNodeIds(new Set()), 2200);
          setScene((current) => {
            const graph = sameCutoff ? mergeGraph(current, delta) : delta;
            return sameCutoff
              ? { ...current, ...graph, question: requestedQuestion, brief: null, trace: [], gaps: [] }
              : { ...emptyScene, ...graph, question: requestedQuestion, conversation: current.conversation };
          });
          setResearchView("graph");
        },
      );
      if (nextScene.conversation?.intent !== "investigation") {
        setScene((current) => current.nodes.length
          ? { ...current, question: nextScene.question, conversation: nextScene.conversation }
          : nextScene);
        if (nextScene.conversation?.intent === "navigation") {
          const target = nextScene.conversation.navigationTarget?.toLowerCase();
          const match = target
            ? scene.nodes.find((node) => node.label.toLowerCase().includes(target)
              || node.id.toLowerCase().includes(target))
            : undefined;
          if (match) select(match.id, "graph");
        }
      } else {
        setScene((current) => {
          const graph = sameCutoff ? mergeGraph(current, nextScene) : nextScene;
          const evidence = sameCutoff
            ? [...new Map([...current.evidence, ...nextScene.evidence].map((item) => [item.id, item])).values()]
            : nextScene.evidence;
          return { ...nextScene, ...graph, evidence };
        });
        setLatestNodeIds(new Set(nextScene.nodes.map((node) => node.id)));
        setMapRuns((count) => sameCutoff ? count + 1 : 1);
        mapCutoff.current = nextCutoff;
        setVisibleRelationshipTypes((current) => new Set([...current, ...nextScene.edges.map((edge) => edge.label)]));
        if (!sameCutoff) { setSelectedId(null); setPinnedId(null); }
        setResearchView("graph");
      }
      setQuestion("");
      setState("ready");
    } catch (nextError) {
      if (sawGraphDelta) {
        setScene(sameCutoff ? scene : { ...emptyScene, conversation: scene.conversation });
        if (!sameCutoff) {
          setMapRuns(0);
          setLatestNodeIds(new Set());
          setSelectedId(null);
          setPinnedId(null);
        }
      }
      setActiveNodeIds(new Set());
      setError(nextError instanceof Error ? nextError.message : "The investigation failed.");
      setState("failed");
    }
  };
  const dismissGuide = () => {
    setGuideOpen(false);
    requestAnimationFrame(() => guideButtonRef.current?.focus());
  };
  const startGuidedExample = () => {
    setQuestion(guidedQuestion);
    setSelectedId(null);
    dismissGuide();
    void run(guidedQuestion, null);
  };
  const resetThread = async () => {
    try {
      await resetConversation(threadId.current);
      setError(null);
      setActivities([]);
      setScene(emptyScene);
      setMapRuns(0);
      setLatestNodeIds(new Set());
      setActiveNodeIds(new Set());
      mapCutoff.current = null;
      setSelectedId(null);
      setPinnedId(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The conversation reset failed.");
    }
  };

  if (state === "loading") return <main className="boot">Opening the evidence workspace…</main>;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="eyebrow">KG / AGENTIC</span><h1>Evidence Workbench</h1><p>Conversation, graph paths, and sources in one research surface.</p></div>
        <div className="scope-note"><span>ACTIVE SCOPE</span><b>Cement decarbonisation</b><small>{coverage.projectRecords} project records / {coverage.sourceVersions} source versions</small></div>
        <div className="header-actions"><button ref={guideButtonRef} className="text-button" onClick={() => setGuideOpen(true)}>Guide</button><div className="status" role="status"><span className={state === "running" ? "dot working" : "dot"} />{state === "running" ? runningLabel : `${toolCount ?? "..."} research tools available`}</div></div>
      </header>
      {guideOpen && <Guide onDismiss={dismissGuide} onStart={startGuidedExample} />}
      <section className="workspace" aria-label="Evidence research workspace">
        <section className="conversation-workbench" aria-label="Conversation and answer">
          <header className="workbench-heading"><div><span className="eyebrow">CONVERSATION</span><h2>Ask, clarify, decide.</h2></div><p>Ordinary questions stay conversational. Evidence retrieval starts only when it can improve the answer.</p></header>
          <div className="conversation-scroll">
            <ConversationPanel messages={messages} />
            {error && <section className="failure" role="alert"><b>Run failed</b><p>{error}</p></section>}
            {hasStructuredResult && scene.brief ? (
              <section className="answer"><div className="answer-heading"><span className="eyebrow">EVIDENCE-BACKED BRIEF</span><button className="text-button" onClick={() => setResearchView("sources")}>Inspect {scene.evidence.length} sources →</button></div><BriefPanel brief={scene.brief} onCitation={(citation) => select(`evidence:${citation.evidence_id}`, "sources")} /></section>
            ) : messages.length === 0 ? (
              <section className="first-prompt"><span className="eyebrow">START HERE</span><h3>Meet Mira. Bring a question.</h3><p>Ask for a definition, explore what this corpus can support, or request an evidence-backed decision. The workspace will show when the graph is—and is not—being used.</p></section>
            ) : null}
          </div>
          <section className="composer">
            <label htmlFor="question">Your question</label>
            <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void run(); }} rows={3} placeholder="Ask naturally. Try “What is retrofit?”" />
            <div className="composer-footer"><div className="prompt-suggestions" aria-label="Suggested questions">{starterPrompts.map((prompt) => <button key={prompt.label} onClick={() => setQuestion(prompt.question)}>{prompt.label}</button>)}</div><button className="primary" disabled={state === "running" || !question.trim()} onClick={() => void run()}>{state === "running" ? "Working…" : "Send"}</button></div>
            <div className="composer-meta"><details><summary>Historical cutoff</summary><label htmlFor="as-of">Only evidence public by <input id="as-of" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label></details><span>⌘/Ctrl + Enter to send</span><button className="text-button" onClick={resetThread}>Reset thread</button></div>
          </section>
        </section>

        <section className="research-workbench" aria-label="Graph, sources, and tool trace">
          <header className="research-header"><div><span className="eyebrow">RESEARCH MAP</span><h2>{scene.nodes.length ? `${scene.nodes.length} ${scene.nodes.length === 1 ? "element" : "elements"} / ${scene.edges.length} ${scene.edges.length === 1 ? "link" : "links"}` : "Waiting for an evidence run"}</h2>{mapRuns > 0 && <small>{mapRuns} evidence {mapRuns === 1 ? "question" : "questions"} in this map{mapCutoff.current ? ` / public by ${mapCutoff.current}` : ""}</small>}</div><div className="view-tabs" role="group" aria-label="Research view">{(["graph", "sources", "trace"] as ResearchView[]).map((view) => <button key={view} aria-pressed={researchView === view} onClick={() => setResearchView(view)}>{view[0].toUpperCase() + view.slice(1)}{view === "sources" && scene.evidence.length ? ` ${scene.evidence.length}` : ""}</button>)}</div></header>

          {researchView === "graph" && <section className="graph-view">
            <div className={activeNodeIds.size ? "graph-stage is-updating" : "graph-stage"}>
              {scene.nodes.length > 0 && <Suspense fallback={<div className="graph-loading">Rendering returned paths...</div>}><GraphCanvas scene={scene} selectedId={selectedId} pinnedId={pinnedId} visibleKinds={visibleKinds} visibleRelationshipTypes={visibleRelationshipTypes} highlightedNodeIds={highlightedNodeIds} latestNodeIds={latestNodeIds} activeNodeIds={activeNodeIds} viewCommand={viewCommand} onSelect={(id) => select(id)} /></Suspense>}
              {scene.nodes.length === 0 && <div className="graph-empty"><span className="eyebrow">LIVE SUBGRAPH</span><h3>No graph needed yet.</h3><p>An evidence question reveals only the paths and sources returned by that run—not the whole database.</p></div>}
              {activeNodeIds.size > 0 && <div className="graph-live-status" role="status"><i />{activities.at(-1)?.action === "claim_supported" ? `Mira checked ${activeNodeIds.size} cited sources` : `Mira is tracing ${activeNodeIds.size} connected elements`}</div>}
              {scene.nodes.length > 0 && <><GraphTools scene={scene} selected={selected} selectedId={selectedId} selectedConnections={selectedConnections} search={search} searchMatches={searchMatches} visibleKinds={visibleKinds} visibleRelationshipTypes={visibleRelationshipTypes} relationshipTypes={relationshipTypes} onSearch={setSearch} onSelect={(id) => select(id)} onInspect={() => setResearchView("sources")} onAsk={(label) => { setQuestion(`What does the available evidence say about ${label}?`); document.getElementById("question")?.focus(); }} onToggle={toggle} setVisibleKinds={setVisibleKinds} setVisibleRelationshipTypes={setVisibleRelationshipTypes} onReset={resetScene} onZoom={(action) => setViewCommand((current) => ({ action, token: current.token + 1 }))} /><div className="graph-key" aria-label="Graph colours"><span><i className="project" />Projects</span><span><i className="evidence" />Sources</span><span><i className="other" />Other elements</span></div></>}
            </div>
            <p className="surface-note">This map grows as you ask evidence questions. Brighter elements belong to the latest answer; older paths remain available to explore. A new historical cutoff starts a separate map.</p>
          </section>}

          {researchView === "sources" && <section className="sources-view">
            <div className="source-list">{scene.evidence.length ? <EvidencePanel scene={scene} selectedId={selectedId} onSelect={(id) => select(id)} /> : <EmptyResearch title="No retrieved sources" text="Ask an evidence-backed question first. General conversation does not seed or simulate evidence." />}</div>
            <div className="source-detail"><Details node={selected} pinned={pinnedId === selectedId} onPin={() => setPinnedId(pinnedId === selectedId ? null : selectedId)} />{scene.nodes.length > 0 && <GraphIndex nodes={indexNodes} search={search} selectedId={selectedId} onSelect={(id) => select(id)} />}</div>
          </section>}

          {researchView === "trace" && <section className="trace-view">
            <div><span className="eyebrow">PUBLIC TOOL ACTIVITY</span>{activities.length ? <ol className="activity-list">{activities.map((trace, index) => <li key={`${trace.action}-${index}`}><b>{activityTitles[trace.action] ?? trace.action.replaceAll("_", " ")}</b>{trace.count !== undefined && <span>{trace.count} {trace.action === "evidence_found" ? "sources" : trace.action === "retrieved_path" ? "paths" : "claims"}</span>}{trace.detail && <p>{trace.detail}</p>}</li>)}</ol> : <EmptyResearch title="No tool activity" text="A normal conversation should leave this trace empty. Evidence runs disclose their public stages here." />}</div>
            <div className="limits"><span className="eyebrow">KNOWN LIMITS</span><p>This is a bounded research corpus, not all of CORDIS. It currently indexes {coverage.projectRecords} project records, {coverage.resultMetadataRecords} result metadata records, and {coverage.fullTextRecords} retained public-document versions. Metadata does not establish technical performance.</p>{scene.gaps.map((gap) => <p key={gap}>{gap}</p>)}</div>
          </section>}
        </section>
      </section>
    </main>
  );
}

interface GraphToolsProps {
  scene: Scene;
  selected: SceneNode | null;
  selectedId: string | null;
  selectedConnections: SceneEdge[];
  search: string;
  searchMatches: SceneNode[];
  visibleKinds: Set<string>;
  visibleRelationshipTypes: Set<string>;
  relationshipTypes: string[];
  onSearch: (value: string) => void;
  onSelect: (id: string) => void;
  onInspect: () => void;
  onAsk: (label: string) => void;
  onToggle: (value: string, update: React.Dispatch<React.SetStateAction<Set<string>>>) => void;
  setVisibleKinds: React.Dispatch<React.SetStateAction<Set<string>>>;
  setVisibleRelationshipTypes: React.Dispatch<React.SetStateAction<Set<string>>>;
  onReset: () => void;
  onZoom: (action: "fit" | "in" | "out") => void;
}

function GraphTools({ scene, selected, selectedId, selectedConnections, search, searchMatches, visibleKinds, visibleRelationshipTypes, relationshipTypes, onSearch, onSelect, onInspect, onAsk, onToggle, setVisibleKinds, setVisibleRelationshipTypes, onReset, onZoom }: GraphToolsProps) {
  return <>
    <div className="graph-tools">
      <label htmlFor="graph-search">Find in this map</label>
      <input id="graph-search" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Project, source, organisation" />
      {search.trim() && <div className="graph-search-results" aria-label="Matching graph elements">
        {searchMatches.slice(0, 7).map((node) => <button key={node.id} onClick={() => { onSelect(node.id); onSearch(""); }}><span>{node.kind}</span>{node.label}</button>)}
        {searchMatches.length === 0 && <p>No matching element in this map.</p>}
      </div>}
    </div>
    <div className="graph-zoom" aria-label="Graph navigation">
      <button aria-label="Zoom in" onClick={() => onZoom("in")}>+</button>
      <button aria-label="Zoom out" onClick={() => onZoom("out")}>-</button>
      <button onClick={() => onZoom("fit")}>Fit</button>
      <button onClick={onReset}>Reset</button>
    </div>
    {selected && <aside className="graph-inspector" id="details" tabIndex={-1} aria-label="Selected graph element">
      <span className="eyebrow">{selected.kind} / {selectedConnections.length} links</span>
      <h3>{selected.label}</h3>
      <p>{selected.kind === "evidence" ? "A retrieved public source linked to the elements it describes." : "Follow a connection to see how this element relates to the evidence."}</p>
      <div className="graph-neighbors">{selectedConnections.slice(0, 5).map((edge) => {
        const neighbor = scene.nodes.find((node) => node.id === (edge.source === selectedId ? edge.target : edge.source));
        return neighbor && <button key={edge.id} onClick={() => onSelect(neighbor.id)}><span>{edge.label.replace(/([A-Z])/g, " $1")}</span>{neighbor.label}</button>;
      })}</div>
      <div className="inspector-actions"><button onClick={() => onAsk(selected.label)}>Ask about this</button><button onClick={onInspect}>Details and sources</button></div>
    </aside>}
    <details className="graph-filters"><summary>Filter elements and links</summary>
      <div className="graph-legend" aria-label="Graph legend">{allKinds.slice(0, 5).map((kind) => <label key={kind}><input type="checkbox" checked={visibleKinds.has(kind)} onChange={() => onToggle(kind, setVisibleKinds)} /><i className={`legend-mark ${kind}`} />{kind}</label>)}</div>
      <div className="relationship-row" aria-label="Relationship filters">{relationshipTypes.map((relationship) => <label key={relationship}><input type="checkbox" checked={visibleRelationshipTypes.has(relationship)} onChange={() => onToggle(relationship, setVisibleRelationshipTypes)} />{relationship.replace(/([A-Z])/g, " $1")}</label>)}</div>
    </details>
  </>;
}

function Guide({ onDismiss, onStart }: { onDismiss: () => void; onStart: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => dialogRef.current?.focus(), []);
  const keepFocusInside = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") { event.preventDefault(); onDismiss(); return; }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled])")];
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  return <div className="guide-backdrop"><section ref={dialogRef} className="guide" role="dialog" aria-modal="true" aria-labelledby="guide-title" tabIndex={-1} onKeyDown={keepFocusInside}><span className="eyebrow">HOW TO USE THE WORKBENCH</span><h2 id="guide-title">Conversation first. Evidence when it helps.</h2><p>Ask naturally. A research question can reveal a live working subgraph; citations open the exact source record and its provenance.</p><ol><li><b>Ask</b> a question or request a decision.</li><li><b>Read</b> the answer in the conversation workspace.</li><li><b>Audit</b> its graph, sources, and public tool trace.</li></ol><p className="hint">The corpus is intentionally bounded. The interface will not present ordinary chat or selected nodes as evidence.</p><div className="guide-actions"><button className="text-button" onClick={onDismiss}>Close</button><button className="primary" onClick={onStart}>Try a cited example</button></div></section></div>;
}

function ConversationPanel({ messages }: { messages: ConversationMessage[] }) {
  if (!messages.length) return null;
  return <section className="conversation" aria-label="Conversation history">{messages.map((message, index) => <article key={`${message.role}-${index}`} className={message.role}><b>{message.role === "user" ? "You" : "Mira"}</b><p>{message.content}</p></article>)}</section>;
}

function BriefPanel({ brief, onCitation }: { brief: NonNullable<Scene["brief"]>; onCitation: (citation: Citation) => void }) {
  return <section className="brief"><StatementView label="Recommendation" statement={brief.recommendation} onCitation={onCitation} /><div className="brief-grid"><StatementView label="Decision" statement={brief.decision} onCitation={onCitation} /><StatementView label="Uncertainty" statement={brief.uncertainty} onCitation={onCitation} /><StatementView label="Next action" statement={brief.next_action} onCitation={onCitation} /></div></section>;
}

function StatementView({ label, statement, onCitation }: { label: string; statement: Statement; onCitation: (citation: Citation) => void }) {
  return <article><h3>{label}</h3><p>{statement.text}</p><div className="citations">{statement.citations.map((citation) => <button key={citation.evidence_id} onClick={() => onCitation(citation)}>Source · {citation.source_category.replaceAll("_", " ")} →</button>)}</div></article>;
}

function EvidencePanel({ scene, selectedId, onSelect }: { scene: Scene; selectedId: string | null; onSelect: (id: string) => void }) {
  return <section className="evidence"><span className="eyebrow">RETRIEVED SOURCES</span>{scene.evidence.map((item, index) => <button className={selectedId === item.nodeId ? "evidence-card selected" : "evidence-card"} key={item.id} onClick={() => onSelect(item.nodeId)}><b>{String(index + 1).padStart(2, "0")} · {item.sourceCategory.replaceAll("_", " ")}</b><span>{item.text}</span><small>{item.publicationYear ? `${item.publicationYear} · year precision` : `Retrieved ${new Date(item.retrievedAt).toLocaleDateString()}`}</small></button>)}</section>;
}

function GraphIndex({ nodes, search, selectedId, onSelect }: { nodes: SceneNode[]; search: string; selectedId: string | null; onSelect: (id: string) => void }) {
  return <section className="graph-index"><details><summary>{search ? `${nodes.length} graph search result(s)` : `Browse ${nodes.length} graph elements`}</summary><div>{nodes.map((node) => <button key={node.id} className={selectedId === node.id ? "selected" : ""} onClick={() => onSelect(node.id)}><b>{node.kind}</b>{node.label}</button>)}</div></details></section>;
}

function Details({ node, pinned, onPin }: { node: SceneNode | null; pinned: boolean; onPin: () => void }) {
  if (!node) return <section id="details" className="details" tabIndex={-1}><span className="eyebrow">SOURCE DETAIL</span><h3>Select a source or graph element.</h3><p>Its identifiers, dates, source category, and provenance will appear here.</p></section>;
  const metadata = Object.entries(node.metadata).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return <section id="details" className="details" tabIndex={-1}><div className="detail-title"><span className="eyebrow">SELECTED {node.kind}</span><button className="text-button" onClick={onPin}>{pinned ? "Unpin" : "Pin focus"}</button></div><h3>{node.label}</h3>{node.source_url && <a href={node.source_url} target="_blank" rel="noreferrer">Open original source ↗</a>}<dl>{metadata.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl></section>;
}

function EmptyResearch({ title, text }: { title: string; text: string }) {
  return <div className="empty-research"><h3>{title}</h3><p>{text}</p></div>;
}

createRoot(document.getElementById("root")!).render(<App />);
