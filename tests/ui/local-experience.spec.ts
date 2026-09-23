import { expect, test, type Page } from "playwright/test";

const baseScene = {
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

async function mockConversation(page: Page, scene: Record<string, unknown>, activities: object[]) {
  await page.route("**/api/conversations", async (route) => {
    const body = [
      ...activities.map((activity) => `event: activity\ndata: ${JSON.stringify(activity)}\n\n`),
      `event: completed\ndata: ${JSON.stringify(scene)}\n\n`,
    ].join("");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });
}

test("treats conversation and research context as peer work areas", async ({ page }) => {
  await page.goto("/");

  const conversation = page.locator(".conversation-workbench");
  const research = page.locator(".research-workbench");
  await expect(conversation).toBeVisible();
  await expect(research).toBeVisible();
  await expect(page.getByRole("button", { name: "Graph" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sources" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Trace" })).toBeVisible();

  const conversationBox = await conversation.boundingBox();
  const researchBox = await research.boundingBox();
  expect(conversationBox!.width).toBeGreaterThan(500);
  expect(researchBox!.width).toBeGreaterThan(500);
});

test("starts honest about scope without forcing an onboarding script", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  await expect(page.getByText("1 bounded evidence tool")).toBeVisible();
  await expect(page.getByText("3 projects · 10 indexed source versions")).toBeVisible();
  await expect(page.getByText("No graph needed yet.")).toBeVisible();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Sources" }).click();
  await expect(page.getByText("No retrieved sources")).toBeVisible();
});

test("ordinary conversation stays readable and does not create graph evidence", async ({ page }) => {
  await mockConversation(page, {
    ...baseScene,
    question: "Hello",
    conversation: {
      threadId: "thread-1",
      selectedNodeIds: [],
      messages: [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hello — what would you like to explore?" },
      ],
      asOf: null,
      intent: "conversation",
      navigationTarget: null,
    },
  }, [{ action: "answered", detail: "No evidence tools used." }]);
  await page.goto("/");

  await expect(page.locator(".prompt-suggestions button")).toHaveCount(4);
  await page.getByLabel("Your question").fill("Hello");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  await expect(page.getByText("Hello — what would you like to explore?")).toBeVisible();
  await expect(page.getByText("Waiting for an evidence run")).toBeVisible();
  await page.getByRole("button", { name: "Trace" }).click();
  await expect(page.getByText("No evidence tools used.")).toBeVisible();
  const historyBox = await page.locator(".conversation").boundingBox();
  const composerBox = await page.locator(".composer").boundingBox();
  expect(historyBox!.y).toBeLessThan(composerBox!.y);
});

test("a cited run connects the readable brief to sources, graph, and trace", async ({ page }) => {
  const citation = {
    evidence_id: "cordis:cemcap:publication:v1",
    source_url: "https://example.test/cemcap.pdf",
    source_category: "publication_full_text",
    passage: "Pilot tests reproduced cement-plant flue-gas conditions.",
    content_hash: "sha256:test",
  };
  const statement = { text: "Validate the capture pathway before pre-FEED.", citations: [citation] };
  const scene = {
    ...baseScene,
    question: "Compare the projects",
    nodes: [
      { id: "project:cemcap", label: "CEMCAP · 641185", kind: "project", source_url: null, metadata: { identifier: "641185" } },
      { id: "evidence:cordis:cemcap:publication:v1", label: "CEMCAP · publication full text", kind: "evidence", source_url: citation.source_url, metadata: { sourceCategory: citation.source_category, passage: citation.passage } },
    ],
    edges: [{ id: "support", source: "evidence:cordis:cemcap:publication:v1", target: "project:cemcap", label: "supports", source_url: citation.source_url, metadata: {} }],
    evidence: [{ id: citation.evidence_id, nodeId: "evidence:cordis:cemcap:publication:v1", kind: "source_reported_claim", text: citation.passage, passage: citation.passage, sourceUrl: citation.source_url, sourceCategory: citation.source_category, contentHash: citation.content_hash, corpusId: "cordis-eurio:cement-retrofit-v1", retrievedAt: "2026-09-23T00:00:00Z", publicationYear: 2018, publicationPrecision: "year", eventAt: null, updatedAt: null, ingestedAt: "2026-09-20T00:00:00Z", canonicalEntityIds: ["project:cemcap"] }],
    brief: { decision: statement, recommendation: statement, alternatives: [], uncertainty: statement, next_action: statement, claims: [statement] },
    conversation: { threadId: "thread-1", selectedNodeIds: [], messages: [{ role: "user", content: "Compare the projects" }, { role: "assistant", content: statement.text }], asOf: null, intent: "investigation", navigationTarget: null },
  };
  await mockConversation(page, scene, [
    { action: "planned", detail: "Starting a live evidence investigation for this question." },
    { action: "retrieved_path", count: 1 },
    { action: "evidence_found", count: 1 },
    { action: "claim_supported", count: 1 },
  ]);
  await page.goto("/");
  await page.getByLabel("Your question").fill("Compare the projects");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  await expect(page.getByText("EVIDENCE-BACKED BRIEF")).toBeVisible();
  await expect(page.getByText(statement.text).first()).toBeVisible();
  await page.getByRole("button", { name: /Source · publication full text/ }).first().click();
  await expect(page.getByText("SELECTED EVIDENCE")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open original source ↗" })).toBeVisible();
  await page.getByRole("button", { name: "Trace" }).click();
  await expect(page.getByText("evidence found")).toBeVisible();
});
