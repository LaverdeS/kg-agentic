import { expect, test } from "playwright/test";

test("recorded conversation keeps citation focus and public activity synchronized", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => localStorage.removeItem("kg-agentic-guide-dismissed"));
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Evidence constellation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Quick guide" })).not.toBeVisible();
  await page.getByLabel("Consulting question").fill("Which CEMCAP evidence should I inspect next?");
  await page.getByRole("button", { name: "Ask recorded walkthrough" }).click();

  await expect(page.getByText("planned").last()).toBeVisible();
  await expect(page.getByText("claim supported").last()).toBeVisible();
  await expect(page.getByText("THREAD MEMORY")).toBeVisible();
  await expect(page.getByRole("paragraph").filter({ hasText: "Which CEMCAP evidence should" })).toBeVisible();

  await page.getByRole("button", { name: /CEMCAP D4.5/i }).click();
  await expect(page.getByText("INSPECTED EVIDENCE")).toBeVisible();
  await expect(page.locator("body")).toContainText("public deliverable full text");
  await page.getByText(/Browse \d+ graph elements/).click();
  const keyboardEvidence = page.getByRole("button", { name: /evidence:.*public deliverable/i });
  await keyboardEvidence.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#details")).toContainText("CEMCAP");

  await page.getByLabel("Consulting question").fill("What does this selected source establish?");
  await page.getByRole("button", { name: "Ask recorded walkthrough" }).click();
  await expect(page.getByText("Using 1 selected graph element").last()).toBeVisible();
  await expect(page.getByText("Recorded walkthrough: this replays a fixed cited brief.").last()).toBeVisible();
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

  await page.getByLabel("Consulting question").fill("What is this app and what data can it use?");
  await page.getByRole("button", { name: "Ask recorded walkthrough" }).click();
  await expect(page.getByText("does not query live services")).toBeVisible();
  await expect(page.getByText("retrieved path")).not.toBeVisible();

  await page.getByLabel("Consulting question").fill("Focus CEMCAP D4.5");
  await page.getByRole("button", { name: "Ask recorded walkthrough" }).click();
  await expect(page.getByText("This is navigation only")).toBeVisible();
});
