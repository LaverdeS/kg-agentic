import type { Scene, Trace } from "./types";

export interface Health {
  status: string;
  mode: "live-only";
  toolCount: number;
  coverage: {
    projectRecords: number;
    resultMetadataRecords: number;
    fullTextRecords: number;
    sourceVersions: number;
  };
}

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health", { cache: "no-store" });
  if (!response.ok) throw new Error(`Service check failed (${response.status}).`);
  return response.json() as Promise<Health>;
}

export interface ConversationInput {
  question: string;
  threadId: string;
  selectedNodeIds: string[];
  asOf: string | null;
}

export async function streamConversation(
  input: ConversationInput,
  onActivity: (trace: Trace) => void,
  onGraphDelta: (delta: Pick<Scene, "nodes" | "edges">) => void,
): Promise<Scene> {
  const response = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok || !response.body) {
    const failure = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(failure.error ?? `Conversation request failed (${response.status}).`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const messages = buffer.split("\n\n");
    buffer = messages.pop() ?? "";
    for (const message of messages) {
      const event = message.match(/^event: (.+)$/m)?.[1];
      const data = message.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data) as Scene | Trace | { message: string; errorType?: string };
      if (event === "activity") onActivity(payload as Trace);
      if (event === "graph_delta") onGraphDelta(payload as Pick<Scene, "nodes" | "edges">);
      if (event === "completed") {
        await reader.cancel();
        return payload as Scene;
      }
      if (event === "failed") {
        await reader.cancel();
        throw new Error((payload as { message: string }).message);
      }
    }
    if (done) break;
  }
  throw new Error("The conversation ended without a completed investigation.");
}

export async function resetConversation(threadId: string): Promise<void> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(threadId)}`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Conversation reset failed (${response.status}).`);
}
