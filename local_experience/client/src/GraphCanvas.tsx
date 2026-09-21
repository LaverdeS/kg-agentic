import Graph from "graphology";
import Sigma from "sigma";
import { useEffect, useRef } from "react";
import type { Scene, SceneNode } from "./types";

const COLORS: Record<SceneNode["kind"], string> = {
  project: "#a78bfa",
  organization: "#e5e7eb",
  role: "#70727e",
  output: "#8b90a0",
  evidence: "#f6b75a",
  entity: "#a1a1aa",
};

function coordinate(value: string, offset: number): number {
  const hash = [...value].reduce((total, character) => (total * 31 + character.charCodeAt(0)) >>> 0, offset);
  return 0.12 + ((hash % 760) / 1000);
}

interface GraphCanvasProps {
  scene: Scene;
  selectedId: string | null;
  pinnedId: string | null;
  visibleKinds: Set<string>;
  onSelect: (id: string) => void;
}

export function GraphCanvas({ scene, selectedId, pinnedId, visibleKinds, onSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const graph = new Graph();
    const visibleNodes = scene.nodes.filter((node) => visibleKinds.has(node.kind));
    for (const node of visibleNodes) {
      graph.addNode(node.id, {
        label: node.label,
        x: coordinate(node.id, 17),
        y: coordinate(node.id, 91),
        size: node.kind === "evidence" ? 11 : node.kind === "project" ? 10 : 7,
        color: COLORS[node.kind],
      });
    }
    for (const edge of scene.edges) {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
          label: edge.label,
          color: "#34323d",
          size: 1.5,
          type: "arrow",
        });
      }
    }
    const renderer = new Sigma(graph, container, {
      renderEdgeLabels: false,
      enableEdgeEvents: false,
      labelDensity: 1.3,
      labelGridCellSize: 80,
      labelRenderedSizeThreshold: 6,
      labelColor: { color: "#d8d6df" },
      labelSize: 12,
      zIndex: true,
    });
    renderer.setSetting("nodeReducer", (node, data) => ({
      ...data,
      highlighted: node === selectedId || node === pinnedId,
      color: node === selectedId ? "#ffffff" : data.color,
      size: node === selectedId ? data.size + 3 : data.size,
    }));
    const focusId = pinnedId ?? selectedId;
    if (focusId && graph.hasNode(focusId)) {
      const { x, y } = graph.getNodeAttributes(focusId);
      renderer.getCamera().setState({ x, y, ratio: 0.65 });
    }
    renderer.on("clickNode", ({ node }) => onSelect(node));
    sigmaRef.current = renderer;
    return () => renderer.kill();
  }, [scene, selectedId, pinnedId, visibleKinds, onSelect]);

  return <div className="graph-canvas" ref={containerRef} aria-hidden="true" />;
}
