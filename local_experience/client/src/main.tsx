import { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { getRecordedScene, streamInvestigation } from "./api";
import { GraphCanvas } from "./GraphCanvas";
import type { Citation, Scene, SceneNode, Statement, Trace } from "./types";
import "./style.css";

const allKinds = ["project", "organization", "role", "output", "evidence", "entity"];

function App() {
  const [scene, setScene] = useState<Scene | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>(null);
  const [visibleKinds, setVisibleKinds] = useState(new Set(allKinds));
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"recorded" | "live">("recorded");
  const [activities, setActivities] = useState<Trace[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "running" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRecordedScene()
      .then((nextScene) => {
        setScene(nextScene);
        setQuestion(nextScene.question);
        setActivities(nextScene.trace);
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

  const select = useCallback((id: string) => setSelectedId(id), []);
  const run = async () => {
    if (!question.trim()) return;
    setState("running");
    setError(null);
    setActivities([]);
    try {
      const nextScene = await streamInvestigation(
        question,
        mode,
        (trace) => setActivities((current) => [...current, trace]),
        (delta) => setScene((current) => (current ? { ...current, ...delta, question } : current)),
      );
      setScene(nextScene);
      setState("ready");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The investigation failed.");
      setState("failed");
    }
  };

  if (!scene && state === "loading") return <main className="boot">Loading local evidence scene…</main>;
  if (!scene) return <main className="boot">The local API is unavailable: {error}</main>;

  return (
    <main>
      <header className="topbar">
        <div><span className="eyebrow">KG / AGENTIC</span><h1>Evidence constellation</h1></div>
        <div className="status"><span className="dot" /> {scene.mode === "recorded" ? "Recorded local snapshot" : "Live core run"}</div>
      </header>
      <section className="workspace" aria-label="Investigation workspace">
        <div className="graph-region">
          <div className="graph-header">
            <div><span className="eyebrow">CURRENT DECISION</span><p>Evidence-led cement retrofit diligence</p></div>
            <button className="quiet" onClick={() => { setSelectedId(null); setPinnedId(null); setVisibleKinds(new Set(allKinds)); }}>Reset scene</button>
          </div>
          <GraphCanvas scene={scene} selectedId={selectedId} pinnedId={pinnedId} visibleKinds={visibleKinds} onSelect={select} />
          <div className="legend" aria-label="Graph legend">
            {allKinds.slice(0, 5).map((kind) => <span key={kind}><i className={`legend-mark ${kind}`} />{kind}</span>)}
          </div>
          <div className="filter-row" aria-label="Graph filters">
            {allKinds.slice(0, 5).map((kind) => (
              <label key={kind}><input type="checkbox" checked={visibleKinds.has(kind)} onChange={() => setVisibleKinds((current) => {
                const next = new Set(current); next.has(kind) ? next.delete(kind) : next.add(kind); return next;
              })} /> {kind}</label>
            ))}
          </div>
          <div className="scene-index" aria-label="Keyboard-accessible graph index">
            {scene.nodes.map((node) => <button key={node.id} className={selectedId === node.id ? "selected" : ""} onClick={() => select(node.id)}>{node.kind}: {node.label}</button>)}
          </div>
        </div>
        <aside className="rail">
          <section className="prompt-card">
            <span className="eyebrow">ASK THE INVESTIGATION</span>
            <label htmlFor="question">Consulting question</label>
            <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} />
            <label className="mode"><input type="radio" checked={mode === "recorded"} onChange={() => setMode("recorded")} /> Recorded walkthrough</label>
            <label className="mode"><input type="radio" checked={mode === "live"} onChange={() => setMode("live")} /> Live core run</label>
            <button className="primary" disabled={state === "running"} onClick={run}>{state === "running" ? "Investigating…" : mode === "live" ? "Run live investigation" : "Replay recorded walkthrough"}</button>
            <p className="hint">Recorded mode replays fixed, labelled evidence; editing its question changes only run context. Live mode invokes the same core use case as the CLI and reports service failures honestly.</p>
          </section>
          <section className="activity-card" aria-live="polite"><span className="eyebrow">PUBLIC ACTIVITY</span>
            {activities.map((trace, index) => <p key={`${trace.action}-${index}`}><b>{trace.action.replaceAll("_", " ")}</b>{trace.count !== undefined ? ` · ${trace.count}` : ""}{trace.detail ? ` · ${trace.detail}` : ""}</p>)}
          </section>
          {error && <section className="failure" role="alert">{error}</section>}
          {scene.brief && <BriefPanel brief={scene.brief} onCitation={(citation) => select(`evidence:${citation.evidence_id}`)} />}
          <EvidencePanel scene={scene} selectedId={selectedId} onSelect={select} />
          <Details node={selected} pinned={pinnedId === selectedId} onPin={() => setPinnedId(pinnedId === selectedId ? null : selectedId)} />
          <section className="gaps"><span className="eyebrow">LIMITS & GAPS</span>{scene.gaps.map((gap) => <p key={gap}>{gap}</p>)}</section>
        </aside>
      </section>
    </main>
  );
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
  return <article><h2>{label}</h2><p>{statement.text}</p><div className="citations">{statement.citations.map((citation) => <button key={citation.evidence_id} onClick={() => onCitation(citation)}>Evidence ↗</button>)}</div></article>;
}

function EvidencePanel({ scene, selectedId, onSelect }: { scene: Scene; selectedId: string | null; onSelect: (id: string) => void }) {
  return <section className="evidence"><span className="eyebrow">RETRIEVED EVIDENCE</span>{scene.evidence.map((item) => <button className={selectedId === item.nodeId ? "evidence-card selected" : "evidence-card"} key={item.id} onClick={() => onSelect(item.nodeId)}><b>{item.sourceCategory.replaceAll("_", " ")} · {item.kind.replaceAll("_", " ")}</b><span>{item.text}</span><small>{item.publicationYear ? `${item.publicationYear} · year precision` : `Retrieved ${new Date(item.retrievedAt).toLocaleDateString()}`}</small></button>)}</section>;
}

function Details({ node, pinned, onPin }: { node: SceneNode | null; pinned: boolean; onPin: () => void }) {
  if (!node) return <section className="details"><span className="eyebrow">INSPECT</span><p>Select a constellation point, evidence card, or graph-index item to inspect its source-qualified metadata.</p></section>;
  const metadata = Object.entries(node.metadata).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return <section className="details"><div className="detail-title"><span className="eyebrow">INSPECTED {node.kind}</span><button className="quiet" onClick={onPin}>{pinned ? "Unpin" : "Pin"}</button></div><h2>{node.label}</h2>{node.source_url && <a href={node.source_url} target="_blank" rel="noreferrer">Open source ↗</a>}<dl>{metadata.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl></section>;
}

createRoot(document.getElementById("root")!).render(<App />);
