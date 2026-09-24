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
  return (hash % 1000) / 1000;
}

type Position = { x: number; y: number };

function placeNodes(scene: Scene, previous: Map<string, Position>): Map<string, Position> {
  const positions = new Map(previous);
  const projects = scene.nodes.filter((node) => node.kind === "project").sort((a, b) => a.id.localeCompare(b.id));
  projects.forEach((node, index) => {
    if (positions.has(node.id)) return;
    const angle = (index / Math.max(projects.length, 1)) * Math.PI * 2 - Math.PI / 2;
    positions.set(node.id, { x: Math.cos(angle) * 5, y: Math.sin(angle) * 5 });
  });
  const newIds = new Set<string>();
  for (const node of scene.nodes) {
    if (positions.has(node.id)) continue;
    const adjacent = scene.edges
      .filter((edge) => edge.source === node.id || edge.target === node.id)
      .map((edge) => positions.get(edge.source === node.id ? edge.target : edge.source))
      .filter((position): position is Position => Boolean(position));
    const anchor = adjacent[0] ?? { x: 0, y: 0 };
    const angle = coordinate(node.id, 17) * Math.PI * 2;
    positions.set(node.id, { x: anchor.x + Math.cos(angle) * 1.5, y: anchor.y + Math.sin(angle) * 1.5 });
    newIds.add(node.id);
  }
  // Settle newcomers around their links without moving the existing mental map.
  const nodes = scene.nodes.map((node) => node.id);
  for (let step = 0; step < 65; step++) {
    for (const id of newIds) {
      const current = positions.get(id)!;
      let dx = 0;
      let dy = 0;
      for (const otherId of nodes) {
        if (otherId === id) continue;
        const other = positions.get(otherId)!;
        const vx = current.x - other.x;
        const vy = current.y - other.y;
        const distance = Math.max(vx * vx + vy * vy, 0.04);
        dx += (vx / distance) * 0.045;
        dy += (vy / distance) * 0.045;
      }
      for (const edge of scene.edges) {
        const neighborId = edge.source === id ? edge.target : edge.target === id ? edge.source : null;
        if (!neighborId) continue;
        const neighbor = positions.get(neighborId)!;
        dx += (neighbor.x - current.x) * 0.012;
        dy += (neighbor.y - current.y) * 0.012;
      }
      positions.set(id, { x: current.x + dx, y: current.y + dy });
    }
  }
  return positions;
}

interface GraphCanvasProps {
  scene: Scene;
  selectedId: string | null;
  pinnedId: string | null;
  visibleKinds: Set<string>;
  visibleRelationshipTypes: Set<string>;
  highlightedNodeIds: Set<string>;
  latestNodeIds: Set<string>;
  activeNodeIds: Set<string>;
  viewCommand: { action: "fit" | "in" | "out"; token: number };
  onSelect: (id: string) => void;
}

const EDGE_COLORS: Record<string, string> = {
  supports: "#f6b75a",
  hasResult: "#8d7dd3",
  hasInvolvedParty: "#70717d",
  isRoleOf: "#4e515e",
};

export function GraphCanvas({ scene, selectedId, pinnedId, visibleKinds, visibleRelationshipTypes, highlightedNodeIds, latestNodeIds, activeNodeIds, viewCommand, onSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const positionsRef = useRef(new Map<string, Position>());
  const cameraStateRef = useRef({ x: 0.5, y: 0.5, ratio: 1, angle: 0 });
  const lastFocusRef = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const graph = new Graph();
    positionsRef.current = placeNodes(scene, positionsRef.current);
    const visibleNodes = scene.nodes.filter((node) => visibleKinds.has(node.kind));
    for (const node of visibleNodes) {
      const position = positionsRef.current.get(node.id)!;
      graph.addNode(node.id, {
        label: node.label,
        x: position.x,
        y: position.y,
        size: node.kind === "evidence" ? 11 : node.kind === "project" ? 10 : 7,
        color: COLORS[node.kind],
      });
    }
    const visibleEdges = scene.edges.filter((edge) => visibleRelationshipTypes.has(edge.label));
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
      renderLabels: true,
      enableEdgeEvents: false,
      labelDensity: 1.3,
      labelGridCellSize: 80,
      labelRenderedSizeThreshold: 6,
      labelColor: { color: "#d8d6df" },
      labelSize: 12,
      zIndex: true,
    });
    renderer.getCamera().setState(cameraStateRef.current);
    renderer.on("clickNode", ({ node }) => onSelectRef.current(node));
    sigmaRef.current = renderer;
    return () => {
      cameraStateRef.current = renderer.getCamera().getState();
      renderer.kill();
      sigmaRef.current = null;
    };
  }, [scene.nodes, scene.edges, visibleKinds, visibleRelationshipTypes]);

  useEffect(() => {
    const renderer = sigmaRef.current;
    if (!renderer) return;
    const graph = renderer.getGraph();
    const kinds = new Map(scene.nodes.map((node) => [node.id, node.kind]));
    const focusId = selectedId ?? pinnedId;
    const neighborhood = new Set<string>();
    if (focusId) {
      neighborhood.add(focusId);
      for (const edge of scene.edges) {
        if (!visibleRelationshipTypes.has(edge.label)) continue;
        if (edge.source === focusId) neighborhood.add(edge.target);
        if (edge.target === focusId) neighborhood.add(edge.source);
      }
    }
    renderer.setSetting("nodeReducer", (node, data) => ({
      ...data,
      color: node === selectedId ? "#ffffff" : activeNodeIds.has(node) ? "#f0d7a5" : focusId && !neighborhood.has(node) ? "#292731" : latestNodeIds.size && !latestNodeIds.has(node) ? "#484650" : data.color,
      highlighted: false,
      label: kinds.get(node) === "project" || node === selectedId || focusId && neighborhood.has(node) ? data.label : "",
      size: node === selectedId || highlightedNodeIds.has(node) || activeNodeIds.has(node) ? data.size + 3 : data.size,
    }));
    renderer.setSetting("edgeReducer", (edge, data) => ({
      ...data,
      color: latestNodeIds.size && !latestNodeIds.has(graph.source(edge)) && !latestNodeIds.has(graph.target(edge)) ? "#33323b" : data.color,
      size: latestNodeIds.size && !latestNodeIds.has(graph.source(edge)) && !latestNodeIds.has(graph.target(edge)) ? 0.65 : data.size,
    }));
    renderer.refresh();
    if (focusId && focusId !== lastFocusRef.current && graph.hasNode(focusId)) {
      const { x, y } = graph.getNodeAttributes(focusId);
      const framed = renderer.viewportToFramedGraph(renderer.graphToViewport({ x, y }));
      renderer.getCamera().setState({ x: framed.x + 0.16, y: framed.y, ratio: Math.min(renderer.getCamera().getState().ratio, 0.65) });
    }
    lastFocusRef.current = focusId;
  }, [scene.nodes, scene.edges, selectedId, pinnedId, visibleRelationshipTypes, highlightedNodeIds, latestNodeIds, activeNodeIds]);

  useEffect(() => {
    const camera = sigmaRef.current?.getCamera();
    if (!camera) return;
    if (viewCommand.action === "fit") camera.setState({ x: 0.5, y: 0.5, ratio: 1 });
    else camera.setState({ ratio: Math.max(0.15, Math.min(3, camera.getState().ratio * (viewCommand.action === "in" ? 0.7 : 1.4))) });
  }, [viewCommand]);

  return <div className="graph-canvas" ref={containerRef} aria-hidden="true" />;
}
