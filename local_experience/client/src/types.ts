export type NodeKind = "project" | "organization" | "role" | "output" | "evidence" | "entity";

export interface SceneNode {
  id: string;
  label: string;
  kind: NodeKind;
  source_url: string | null;
  metadata: Record<string, unknown>;
}

export interface SceneEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  source_url: string;
  metadata: Record<string, unknown>;
}

export interface Citation {
  evidence_id: string;
  source_url: string;
  source_category: string;
  passage: string;
  content_hash: string;
}

export interface Statement {
  text: string;
  citations: Citation[];
}

export interface Brief {
  decision: Statement;
  recommendation: Statement;
  alternatives: Statement[];
  uncertainty: Statement;
  next_action: Statement;
  claims: Statement[];
}

export interface Evidence {
  id: string;
  nodeId: string;
  kind: string;
  text: string;
  passage: string | null;
  sourceUrl: string;
  sourceCategory: string;
  contentHash: string;
  corpusId: string;
  retrievedAt: string;
  publicationYear: number | null;
  publicationPrecision: string | null;
  eventAt: string | null;
  updatedAt: string | null;
  ingestedAt: string | null;
  canonicalEntityIds: string[];
}

export interface Trace {
  action: string;
  count?: number;
  detail?: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Conversation {
  threadId: string;
  selectedNodeIds: string[];
  messages: ConversationMessage[];
  asOf: string | null;
  intent?: "investigation" | "help" | "navigation";
  navigationTarget?: string | null;
}

export interface Scene {
  question: string;
  status: string;
  mode: "recorded" | "live";
  nodes: SceneNode[];
  edges: SceneEdge[];
  evidence: Evidence[];
  brief: Brief | null;
  trace: Trace[];
  gaps: string[];
  usage?: Record<string, number>;
  conversation?: Conversation;
}
