import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { getRecordedScene, resetConversation, streamConversation } from "./api";
import { GraphCanvas } from "./GraphCanvas";
import type { Citation, ConversationMessage, Scene, SceneNode, Statement, Trace } from "./types";
import "./style.css";

const allKinds = ["project", "organization", "role", "output", "evidence", "entity"];
const guidedQuestion = "Which CEMCAP evidence should I inspect first?";
const guideStorageKey = "kg-agentic-guide-dismissed";

function hasSameGraph(current: Scene, next: Pick<Scene, "nodes" | "edges">) {
  return current.nodes.length === next.nodes.length
    && current.edges.length === next.edges.length
    && current.nodes.every((node, index) => node.id === next.nodes[index]?.id)
    && current.edges.every((edge, index) => edge.id === next.edges[index]?.id);
}

function App() {
  const [scene, setScene] = useState<Scene | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>(null);
  const [visibleKinds, setVisibleKinds] = useState(new Set(allKinds));
  const [visibleRelationshipTypes, setVisibleRelationshipTypes] = useState(new Set<string>());
  const [search, setSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"recorded" | "live">("recorded");
  const [asOf, setAsOf] = useState("");
  const [activities, setActivities] = useState<Trace[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "running" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);
  const [guideOpen, setGuideOpen] = useState(
    () => window.localStorage.getItem(guideStorageKey) !== "true",
  );
  const threadId = useRef(crypto.randomUUID());

  useEffect(() => {
    getRecordedScene()
      .then((nextScene) => {
        setScene(nextScene);
        setQuestion(nextScene.question);
        setActivities(nextScene.trace);
        setVisibleRelationshipTypes(new Set(nextScene.edges.map((edge) => edge.label)));
        setState("ready");
      })
      .catch((nextError: Error) => {
        setError(nextError.message);
        setState("failed");
      });
  }, []);

  const selected = useMemo(
    () => scene?.nodes.find((node) => node.id === selectedId) ?? null,
    [scene, selectedId],
  );
  const relationshipTypes = useMemo(
    () => [...new Set(scene?.edges.map((edge) => edge.label) ?? [])].sort(),
    [scene],
  );
  const searchMatches = useMemo(
    () => search.trim()
      ? scene?.nodes.filter((node) => node.label.toLowerCase().includes(search.toLowerCase())) ?? []
      : [],
    [scene, search],
  );
  const indexNodes = search.trim() ? searchMatches : scene?.nodes ?? [];
  const messages = scene?.conversation?.messages ?? [];

  const select = useCallback((id: string) => {
    setSelectedId(id);
    requestAnimationFrame(() => document.getElementById("details")?.focus());
  }, []);
  const resetScene = () => {
    setSelectedId(null);
    setPinnedId(null);
    setVisibleKinds(new Set(allKinds));
    setVisibleRelationshipTypes(new Set(relationshipTypes));
    setSearch("");
  };
  const toggle = (value: string, update: React.Dispatch<React.SetStateAction<Set<string>>>) => {
    update((current) => {
      const next = new Set(current);
      next.has(value) ? next.delete(value) : next.add(value);
      return next;
    });
  };
  const run = async (requestedQuestion = question) => {
    if (!requestedQuestion.trim()) return;
    setState("running");
    setError(null);
    setActivities([]);
    try {
      const nextScene = await streamConversation(
        {
          question: requestedQuestion,
          mode,
          threadId: threadId.current,
          selectedNodeIds: selectedId ? [selectedId] : [],
          asOf: mode === "live" && asOf ? asOf : null,
        },
        (trace) => setActivities((current) => [...current, trace]),
        (delta) => setScene((current) => !current || hasSameGraph(current, delta)
          ? current
          : { ...current, ...delta, question: requestedQuestion }),
      );
      if (nextScene.conversation?.intent === "help") {
        setScene((current) => current ? { ...current, conversation: nextScene.conversation } : nextScene);
      } else {
        setScene((current) => current && hasSameGraph(current, nextScene)
          ? { ...current, question: nextScene.question, conversation: nextScene.conversation }
          : nextScene);
        if (!scene || !hasSameGraph(scene, nextScene)) {
          setVisibleRelationshipTypes(new Set(nextScene.edges.map((edge) => edge.label)));
        }
      }
      setState("ready");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The investigation failed.");
      setState("failed");
    }
  };
  const dismissGuide = () => {
    window.localStorage.setItem(guideStorageKey, "true");
    setGuideOpen(false);
  };
  const startGuidedExample = () => {
    setQuestion(guidedQuestion);
    dismissGuide();
    void run(guidedQuestion);
  };
  const resetThread = async () => {
    try {
      await resetConversation(threadId.current);
      setError(null);
      setActivities([]);
      setScene((current) => current ? { ...current, conversation: undefined } : current);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The conversation reset failed.");
    }
  };

  if (!scene && state === "loading") return <main className="boot">Loading local evidence scene…</main>;
  if (!scene) return <main className="boot">The local API is unavailable: {error}</main>;

  return (
    <main>
      <header className="topbar">
        <div><span className="eyebrow">KG / AGENTIC</span><h1>Evidence constellation</h1></div>
        <button className="quiet guide-button" onClick={() => setGuideOpen(true)}>Guide</button>
        <div className="status"><span className="dot" /> {(state === "running" || state === "failed" ? mode : scene.mode) === "recorded" ? "Recorded local snapshot" : asOf ? `Strict historical · ${asOf}` : "Live core run"}</div>
      </header>
      {guideOpen && <Guide onDismiss={dismissGuide} onStart={startGuidedExample} />}
      <section className="workspace" aria-label="Investigation workspace">
        <div className="graph-region">
          <div className="graph-header">
            <div><span className="eyebrow">CURRENT DECISION</span><p>Evidence-led cement retrofit diligence</p></div>
            <button className="quiet" onClick={resetScene}>Reset scene</button>
          </div>
          <GraphCanvas scene={scene} selectedId={selectedId} pinnedId={pinnedId} visibleKinds={visibleKinds} visibleRelationshipTypes={visibleRelationshipTypes} onSelect={select} />
          <div className="graph-tools">
            <label>Search graph<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find evidence, project, organisation" /></label>
            {selected && <p className="selection-chip">Context: {selected.kind} · {selected.label}</p>}
          </div>
          <div className="legend" aria-label="Graph legend">
            {allKinds.slice(0, 5).map((kind) => <span key={kind}><i className={`legend-mark ${kind}`} />{kind}</span>)}
          </div>
          <div className="filter-row" aria-label="Node filters">
            {allKinds.slice(0, 5).map((kind) => (
              <label key={kind}><input type="checkbox" checked={visibleKinds.has(kind)} onChange={() => toggle(kind, setVisibleKinds)} /> {kind}</label>
            ))}
          </div>
          <div className="relationship-row" aria-label="Relationship filters">
            {relationshipTypes.map((relationship) => <label key={relationship}><input type="checkbox" checked={visibleRelationshipTypes.has(relationship)} onChange={() => toggle(relationship, setVisibleRelationshipTypes)} /> {relationship.replace(/([A-Z])/g, " $1")}</label>)}
          </div>
        </div>
        <aside className="rail">
          <section className="prompt-card">
            <span className="eyebrow">CONVERSATION</span>
            <label htmlFor="question">Consulting question</label>
            <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} />
            <fieldset className="mode-group"><legend>Investigation mode</legend><label className="mode"><input type="radio" name="mode" checked={mode === "recorded"} onChange={() => setMode("recorded")} /> Recorded walkthrough</label>
            <label className="mode"><input type="radio" name="mode" checked={mode === "live"} onChange={() => setMode("live")} /> Live core run</label></fieldset>
            <label className="as-of" htmlFor="as-of">Strict historical cutoff<input id="as-of" type="date" value={asOf} disabled={mode === "recorded"} onChange={(event) => setAsOf(event.target.value)} /></label>
            <button className="primary" disabled={state === "running"} onClick={() => void run()}>{state === "running" ? "Investigating…" : mode === "live" ? "Ask live investigation" : "Ask recorded walkthrough"}</button>
            <button className="quiet reset-thread" onClick={resetThread}>Reset conversation</button>
            <p className="hint">A selected graph element is supplied as navigation context, never as evidence. Recorded mode replays a labelled current snapshot. Live historical mode uses only cutoff-eligible evidence and reports unavailable services honestly.</p>
          </section>
          <ConversationPanel messages={messages} />
          <section className="activity-card" aria-live="polite"><span className="eyebrow">PUBLIC ACTIVITY</span>
            {activities.map((trace, index) => <p key={`${trace.action}-${index}`}><b>{trace.action.replaceAll("_", " ")}</b>{trace.count !== undefined ? ` · ${trace.count}` : ""}{trace.detail ? ` · ${trace.detail}` : ""}</p>)}
          </section>
          {error && <section className="failure" role="alert">{error}</section>}
          {scene.brief && <BriefPanel brief={scene.brief} onCitation={(citation) => select(`evidence:${citation.evidence_id}`)} />}
          <EvidencePanel scene={scene} selectedId={selectedId} onSelect={select} />
          <Details node={selected} pinned={pinnedId === selectedId} onPin={() => setPinnedId(pinnedId === selectedId ? null : selectedId)} />
          <GraphIndex nodes={indexNodes} search={search} selectedId={selectedId} onSelect={select} />
          <section className="gaps"><span className="eyebrow">LIMITS & GAPS</span>{scene.gaps.map((gap) => <p key={gap}>{gap}</p>)}</section>
        </aside>
      </section>
    </main>
  );
}

function Guide({ onDismiss, onStart }: { onDismiss: () => void; onStart: () => void }) {
  return <div className="guide-backdrop"><section className="guide" role="dialog" aria-modal="true" aria-labelledby="guide-title">
    <span className="eyebrow">FIRST TWO MINUTES</span><h2 id="guide-title">Quick guide</h2>
    <p>Turn a cement-retrofit question into an auditable recommendation: ask, watch the working graph settle around its support, then inspect the cited source yourself.</p>
    <ol><li><b>Ask</b> a decision question. The recorded walkthrough is a safe, current-only example.</li><li><b>Trace</b> the public activity and select the amber CEMCAP D4.5 evidence card to focus its neighborhood.</li><li><b>Continue</b> with a follow-up. Your selection guides navigation; it never becomes evidence.</li></ol>
    <p className="hint">Use <b>Guide</b> in the header whenever you want this orientation again. Ask “What is this app?” for an honest capability summary without searching.</p>
    <div className="guide-actions"><button className="quiet" onClick={onDismiss}>Skip guide for now</button><button className="primary" onClick={onStart}>Start guided example</button></div>
  </section></div>;
}

function ConversationPanel({ messages }: { messages: ConversationMessage[] }) {
  return <section className="conversation"><span className="eyebrow">THREAD MEMORY</span>{messages.length === 0 ? <p className="hint">Ask a question to start this local, in-memory thread.</p> : messages.map((message, index) => <article key={`${message.role}-${index}`} className={message.role}><b>{message.role === "user" ? "You" : "Investigation"}</b><p>{message.content}</p></article>)}</section>;
}

function BriefPanel({ brief, onCitation }: { brief: NonNullable<Scene["brief"]>; onCitation: (citation: Citation) => void }) {
  return <section className="brief"><span className="eyebrow">SUPPORTED BRIEF</span>
    <StatementView label="Recommendation" statement={brief.recommendation} onCitation={onCitation} />
    <StatementView label="Decision" statement={brief.decision} onCitation={onCitation} />
    <StatementView label="Uncertainty" statement={brief.uncertainty} onCitation={onCitation} />
    <StatementView label="Next action" statement={brief.next_action} onCitation={onCitation} />
  </section>;
}

function StatementView({ label, statement, onCitation }: { label: string; statement: Statement; onCitation: (citation: Citation) => void }) {
  return <article><h2>{label}</h2><p>{statement.text}</p><div className="citations">{statement.citations.map((citation) => <button key={citation.evidence_id} onClick={() => onCitation(citation)}>Focus evidence →</button>)}</div></article>;
}

function EvidencePanel({ scene, selectedId, onSelect }: { scene: Scene; selectedId: string | null; onSelect: (id: string) => void }) {
  return <section className="evidence"><span className="eyebrow">RETRIEVED EVIDENCE</span>{scene.evidence.map((item) => <button className={selectedId === item.nodeId ? "evidence-card selected" : "evidence-card"} key={item.id} onClick={() => onSelect(item.nodeId)}><b>{item.sourceCategory.replaceAll("_", " ")} · {item.kind.replaceAll("_", " ")}</b><span>{item.text}</span><small>{item.publicationYear ? `${item.publicationYear} · year precision` : `Retrieved ${new Date(item.retrievedAt).toLocaleDateString()}`}</small></button>)}</section>;
}

function GraphIndex({ nodes, search, selectedId, onSelect }: { nodes: SceneNode[]; search: string; selectedId: string | null; onSelect: (id: string) => void }) {
  return <section className="graph-index"><details><summary>{search ? `${nodes.length} graph search result(s)` : `Browse ${nodes.length} graph elements`}</summary><div>{nodes.map((node) => <button key={node.id} className={selectedId === node.id ? "selected" : ""} onClick={() => onSelect(node.id)}>{node.kind}: {node.label}</button>)}</div></details></section>;
}

function Details({ node, pinned, onPin }: { node: SceneNode | null; pinned: boolean; onPin: () => void }) {
  if (!node) return <section id="details" className="details" tabIndex={-1}><span className="eyebrow">INSPECT</span><p>Search, select, or focus an evidence card to inspect source-qualified metadata and its immediate graph neighborhood.</p></section>;
  const metadata = Object.entries(node.metadata).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return <section id="details" className="details" tabIndex={-1}><div className="detail-title"><span className="eyebrow">INSPECTED {node.kind}</span><button className="quiet" onClick={onPin}>{pinned ? "Unpin" : "Pin focus"}</button></div><h2>{node.label}</h2>{node.source_url && <a href={node.source_url} target="_blank" rel="noreferrer">Open source →</a>}<dl>{metadata.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl></section>;
}

createRoot(document.getElementById("root")!).render(<App />);
