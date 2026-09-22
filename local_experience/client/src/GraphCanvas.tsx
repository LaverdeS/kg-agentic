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
  visibleRelationshipTypes: Set<string>;
  highlightedNodeIds: Set<string>;
  onSelect: (id: string) => void;
}

const EDGE_COLORS: Record<string, string> = {
  supports: "#f6b75a",
  hasResult: "#8d7dd3",
  hasInvolvedParty: "#70717d",
  isRoleOf: "#4e515e",
};

export function GraphCanvas({ scene, selectedId, pinnedId, visibleKinds, visibleRelationshipTypes, highlightedNodeIds, onSelect }: GraphCanvasProps) {
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
    const visibleEdges = scene.edges.filter((edge) => visibleRelationshipTypes.has(edge.label));
    const focusId = selectedId ?? pinnedId;
    const neighborhood = new Set<string>();
    if (focusId) {
      neighborhood.add(focusId);
      for (const edge of visibleEdges) {
        if (edge.source === focusId) neighborhood.add(edge.target);
        if (edge.target === focusId) neighborhood.add(edge.source);
      }
    }
    for (const edge of visibleEdges) {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
          label: edge.label,
          color: EDGE_COLORS[edge.label] ?? "#34323d",
          size: 1.5,
          type: "arrow",
        });
      }
    }
    const renderer = new Sigma(graph, container, {
      renderEdgeLabels: false,
      renderLabels: window.innerWidth >= 600,
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
      color: node === selectedId ? "#ffffff" : focusId && !neighborhood.has(node) ? "#292731" : highlightedNodeIds.size && !highlightedNodeIds.has(node) ? "#24232a" : data.color,
      highlighted: node === selectedId || node === pinnedId || highlightedNodeIds.has(node),
      label: focusId && !neighborhood.has(node) || highlightedNodeIds.size && !highlightedNodeIds.has(node) ? "" : data.label,
      size: node === selectedId || highlightedNodeIds.has(node) ? data.size + 3 : data.size,
    }));
    renderer.setSetting("edgeReducer", (edge, data) => ({
      ...data,
      color: highlightedNodeIds.size && !highlightedNodeIds.has(graph.source(edge)) && !highlightedNodeIds.has(graph.target(edge)) ? "#201f25" : data.color,
      size: highlightedNodeIds.size && !highlightedNodeIds.has(graph.source(edge)) && !highlightedNodeIds.has(graph.target(edge)) ? 0.45 : data.size,
    }));
    if (focusId && graph.hasNode(focusId)) {
      const { x, y } = graph.getNodeAttributes(focusId);
      renderer.getCamera().setState({ x, y, ratio: 0.65 });
    }
    renderer.on("clickNode", ({ node }) => onSelect(node));
    sigmaRef.current = renderer;
    return () => renderer.kill();
  }, [scene, selectedId, pinnedId, visibleKinds, visibleRelationshipTypes, highlightedNodeIds, onSelect]);

  return <div className="graph-canvas" ref={containerRef} aria-hidden="true" />;
}
