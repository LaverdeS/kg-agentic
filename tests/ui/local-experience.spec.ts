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
  await page.route("**/api/health", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ready", mode: "live-only", toolCount: 2, coverage: { projectRecords: 6, resultMetadataRecords: 10, fullTextRecords: 8, sourceVersions: 24 } }) }));
  await page.goto("/");

  await expect(page.getByText("2 research tools available")).toBeVisible();
  await expect(page.getByText("6 project records / 24 source versions")).toBeVisible();
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
  await expect(page.getByText("Found public sources")).toBeVisible();
});

test("live graph stages grow a searchable map across questions while inspection leaves it intact", async ({ page }, testInfo) => {
  const projectA = { id: "project:a", label: "Project A", kind: "project", source_url: null, metadata: {} };
  const projectB = { id: "project:b", label: "Project B", kind: "project", source_url: null, metadata: {} };
  const output = { id: "output:b", label: "Project B report", kind: "output", source_url: null, metadata: {} };
  const first = { ...baseScene, status: "abstained", nodes: [projectA, output], edges: [{ id: "link:a", source: "project:a", target: "output:b", label: "hasResult", source_url: "https://example.test/a", metadata: {} }] };
  const second = { ...baseScene, status: "abstained", nodes: [projectA, projectB, output], edges: [...first.edges, { id: "link:b", source: "project:b", target: "output:b", label: "hasResult", source_url: "https://example.test/b", metadata: {} }] };
  let turn = 0;
  await page.route("**/api/conversations", async (route) => {
    turn += 1;
    const investigating = turn < 3;
    const graph = turn === 1 ? first : second;
    const scene = {
      ...(investigating ? graph : baseScene),
      conversation: { threadId: "test", selectedNodeIds: [], messages: [{ role: "user", content: "Question" }, { role: "assistant", content: investigating ? "The evidence is incomplete." : "Two projects are in this map." }], asOf: null, intent: investigating ? "investigation" : "inspection", navigationTarget: null },
    };
    const body = [
      investigating ? `event: activity\ndata: ${JSON.stringify({ action: "retrieved_path", count: graph.edges.length })}\n\n` : "",
      investigating ? `event: graph_delta\ndata: ${JSON.stringify({ nodes: graph.nodes, edges: graph.edges })}\n\n` : "",
      `event: completed\ndata: ${JSON.stringify(scene)}\n\n`,
    ].join("");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });
  await page.goto("/");
  await page.getByLabel("Your question").fill("First evidence question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("2 elements / 1 link")).toBeVisible();
  await page.getByLabel("Your question").fill("Second evidence question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("3 elements / 2 links")).toBeVisible();
  await expect(page.getByText("2 evidence questions in this map")).toBeVisible();
  await expect(page.locator(".graph-live-status")).toBeHidden();
  await page.screenshot({ path: testInfo.outputPath("research-map-overview.png"), animations: "disabled" });
  await page.getByLabel("Find in this map").fill("Project B");
  await page.locator(".graph-search-results button").first().click();
  await expect(page.getByRole("complementary", { name: "Selected graph element" })).toContainText("Project B");
  await page.screenshot({ path: testInfo.outputPath("research-map-desktop.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Ask about this" }).click();
  await expect(page.getByLabel("Your question")).toHaveValue(/Project B/);
  await page.getByLabel("Your question").fill("How many projects are in this map?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("3 elements / 2 links")).toBeVisible();
  await expect(page.getByText("Two projects are in this map.")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Fit", exact: true })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Selected graph element" })).toBeVisible();
  await page.locator(".research-workbench").screenshot({ path: testInfo.outputPath("research-map-mobile.png"), animations: "disabled" });
});

test("a failed historical run never pairs its graph with an older cited answer", async ({ page }) => {
  const statement = { text: "Earlier evidence supports a current recommendation.", citations: [] };
  const first = {
    ...baseScene,
    nodes: [{ id: "project:current", label: "Current project", kind: "project", source_url: null, metadata: {} }],
    brief: { decision: statement, recommendation: statement, alternatives: [], uncertainty: statement, next_action: statement, claims: [] },
    conversation: { threadId: "test", selectedNodeIds: [], messages: [{ role: "user", content: "Current question" }, { role: "assistant", content: statement.text }], asOf: null, intent: "investigation" },
  };
  let turn = 0;
  await page.route("**/api/conversations", async (route) => {
    turn += 1;
    const body = turn === 1
      ? `event: completed\ndata: ${JSON.stringify(first)}\n\n`
      : [
          `event: graph_delta\ndata: ${JSON.stringify({ nodes: [{ id: "project:past", label: "Past project", kind: "project", source_url: null, metadata: {} }], edges: [] })}\n\n`,
          `event: failed\ndata: ${JSON.stringify({ message: "Historical source check failed." })}\n\n`,
        ].join("");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });
  await page.goto("/");
  await page.getByLabel("Your question").fill("Current question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("EVIDENCE-BACKED BRIEF")).toBeVisible();

  await page.locator("summary", { hasText: "Historical cutoff" }).click();
  await page.getByLabel("Only evidence public by").fill("2020-01-01");
  await page.getByLabel("Your question").fill("Historical question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Historical source check failed.");
  await expect(page.getByText("EVIDENCE-BACKED BRIEF")).toBeHidden();
  await expect(page.getByText("No graph needed yet.")).toBeVisible();
});

test("mobile-first reduced-motion research stays keyboard navigable", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const node = { id: "project:mobile", label: "Mobile project", kind: "project", source_url: null, metadata: {} };
  await mockConversation(page, {
    ...baseScene,
    status: "abstained",
    nodes: [node],
    conversation: { threadId: "mobile", selectedNodeIds: [], messages: [{ role: "user", content: "Find a project" }, { role: "assistant", content: "I found a project in this research map." }], asOf: null, intent: "investigation", navigationTarget: null },
  }, [{ action: "retrieved_path", count: 0 }]);
  await page.goto("/");
  await page.getByLabel("Your question").fill("Find a project");
  await page.getByLabel("Your question").press("Control+Enter");
  await expect(page.getByText("1 element / 0 links")).toBeVisible();
  await page.getByLabel("Find in this map").fill("Mobile project");
  await page.keyboard.press("Tab");
  await expect(page.locator(".graph-search-results button").first()).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("complementary", { name: "Selected graph element" })).toContainText("Mobile project");
  await expect(page.locator(".graph-canvas canvas").first()).toBeVisible();
  await expect.poll(() => page.locator(".graph-inspector").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  await page.locator(".research-workbench").screenshot({ path: testInfo.outputPath("mobile-first-reduced-motion.png"), animations: "disabled" });
});
