import { expect, test } from "playwright/test";

test("recorded conversation keeps citation focus and public activity synchronized", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => localStorage.removeItem("kg-agentic-guide-dismissed"));
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Evidence navigator" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Quick guide" })).not.toBeVisible();
  await page.getByLabel("Message the explorer").fill("Which CEMCAP evidence should I inspect next?");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText("planned").last()).toBeVisible();
  await expect(page.getByText("claim supported").last()).toBeVisible();
  await expect(page.getByText("LOCAL CONVERSATION")).toBeVisible();
  await expect(page.getByRole("paragraph").filter({ hasText: "Which CEMCAP evidence should" })).toBeVisible();

  await page.getByRole("button", { name: /CEMCAP D4.5/i }).click();
  await expect(page.getByText("INSPECTED EVIDENCE")).toBeVisible();
  await expect(page.locator("body")).toContainText("public deliverable full text");
  await page.getByText(/Browse \d+ graph elements/).click();
  const keyboardEvidence = page.getByRole("button", { name: /evidence:.*public deliverable/i });
  await keyboardEvidence.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#details")).toContainText("CEMCAP");

  await page.getByLabel("Message the explorer").fill("What does this selected source establish?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Using 1 selected graph element").last()).toBeVisible();
  await expect(page.getByText("Recorded example: this is the only recorded example").last()).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches))
    .toBe(true);
});

test("first-use guide starts a cited discovery and help questions leave the graph still", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => localStorage.removeItem("kg-agentic-guide-dismissed"));
  await page.goto("/");

  await expect(page.getByRole("dialog", { name: "Quick guide" })).toBeVisible();
  await page.getByRole("button", { name: "Start guided example" }).click();
  await expect(page.getByText("claim supported").last()).toBeVisible();
  await expect(page.locator("#details")).toContainText("CEMCAP D4.5");

  await page.getByLabel("Message the explorer").fill("What is this app and what data can it use?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("does not search or change the graph")).toBeVisible();
  await expect(page.getByText("retrieved path")).not.toBeVisible();

  await page.getByLabel("Message the explorer").fill("Focus CEMCAP D4.5");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("This is navigation only")).toBeVisible();
});

test("ordinary chat feels welcome and does not start an investigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => localStorage.setItem("kg-agentic-guide-dismissed", "true"));
  await page.goto("/");

  await expect(page.getByText("Ask anything about this workspace or the decision.")).toBeVisible();
  await expect(page.getByText("I’ll clearly say when I’m chatting, focusing the graph, or checking evidence.")).toBeVisible();
  await page.getByLabel("Message the explorer").fill("Hello there");
  await page.getByRole("button", { name: "Send message" }).focus();
  await page.keyboard.press("Enter");

  await expect(page.getByText("No evidence retrieval has started.")).toBeVisible();
  await expect(page.getByText("conversed")).toBeVisible();
  await expect(page.getByText("retrieved path")).not.toBeVisible();
  await expect
    .poll(() => page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches))
    .toBe(true);
});

test("structured evidence is shown only for an investigation and labels the recorded example", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("kg-agentic-guide-dismissed", "true"));
  await page.goto("/");

  await expect(page.getByText("No structured result yet")).toBeVisible();
  await expect(page.getByText("SUPPORTED BRIEF")).not.toBeVisible();
  await expect(page.getByText("RETRIEVED EVIDENCE")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Compare CEMCAP / LEILAC2" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Decision gap" })).toBeVisible();

  await page.getByLabel("Message the explorer").fill("Which CEMCAP evidence should I inspect first?");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText("RECORDED EXAMPLE", { exact: true })).toBeVisible();
  await expect(page.getByText("SUPPORTED BRIEF")).toBeVisible();
  await expect(page.getByText("RETRIEVED EVIDENCE")).toBeVisible();
  await expect(page.getByText("only recorded example")).toBeVisible();
});
