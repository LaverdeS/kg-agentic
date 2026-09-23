import { expect, test } from "playwright/test";

test("starts empty and explains live-only tools without inventing evidence", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => localStorage.setItem("kg-agentic-guide-dismissed", "true"));
  await page.goto("/");

  await expect(page.getByText("3 live tools ready")).toBeVisible();
  await expect(page.getByText("NO RESULT YET")).toBeVisible();
  await expect(page.getByText("SUPPORTED BRIEF", { exact: true })).not.toBeVisible();
  await expect(page.getByText("RETRIEVED EVIDENCE", { exact: true })).not.toBeVisible();
  await expect(page.getByText("Your first live investigation will appear here.")).toBeVisible();

  await page.getByLabel("Message the explorer").fill("What is this app and what tools do you use?");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText("recommended tasks")).toBeVisible();
  await expect(page.getByText("not a recorded example")).toBeVisible();
  await expect(page.getByText("1. Compare CEMCAP and LEILAC2")).toBeVisible();
  await expect(page.getByText("SUPPORTED BRIEF", { exact: true })).not.toBeVisible();
  await expect(page.getByText("RETRIEVED EVIDENCE", { exact: true })).not.toBeVisible();
});

test("chat history stays above the composer and offers six real investigation prompts", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("kg-agentic-guide-dismissed", "true"));
  await page.goto("/");

  await expect(page.locator(".prompt-suggestions button")).toHaveCount(6);
  await page.getByLabel("Message the explorer").fill("Hello");
  await page.getByRole("button", { name: "Send message" }).click();

  const history = page.locator(".conversation");
  const composer = page.locator(".prompt-card");
  await expect(history.getByText("Hello")).toBeVisible();
  await expect(history.getByText("will not reuse an old graph result")).toBeVisible();
  await expect(history.boundingBox()).resolves.toMatchObject({ y: expect.any(Number) });
  const historyBox = await history.boundingBox();
  const composerBox = await composer.boundingBox();
  expect(historyBox!.y).toBeLessThan(composerBox!.y);
});
