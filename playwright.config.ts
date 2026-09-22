import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: "./tests/ui",
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:8000",
    browserName: "chromium",
    channel: "chrome",
    screenshot: "only-on-failure",
  },
});
