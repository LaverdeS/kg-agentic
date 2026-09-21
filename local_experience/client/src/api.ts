import type { Scene, Trace } from "./types";

export async function getRecordedScene(): Promise<Scene> {
  const response = await fetch("/api/scene/recorded");
  if (!response.ok) throw new Error(`Scene request failed (${response.status}).`);
  return response.json() as Promise<Scene>;
}

export async function streamInvestigation(
  question: string,
  mode: "recorded" | "live",
  onActivity: (trace: Trace) => void,
  onGraphDelta: (delta: Pick<Scene, "nodes" | "edges">) => void,
): Promise<Scene> {
  const response = await fetch("/api/investigations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, mode }),
  });
  if (!response.ok || !response.body) throw new Error(`Investigation request failed (${response.status}).`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalScene: Scene | undefined;

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
      if (event === "completed") finalScene = payload as Scene;
      if (event === "failed") throw new Error((payload as { message: string }).message);
    }
    if (done) break;
  }
  if (!finalScene) throw new Error("The API ended without a completed scene.");
  return finalScene;
}
