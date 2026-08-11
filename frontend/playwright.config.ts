import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // Cold CI runs are slow; a tight budget was causing timeouts, not real failures.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "cd .. && python -m uvicorn backend.app:app --port 8000",
      url: "http://localhost:8000/api/readyz",
      reuseExistingServer: !process.env.CI,
      timeout: 90_000,
    },
    {
      // Production build, not `next dev`: dev compiles each route on first request
      // (tens of seconds in CI, blowing the test timeout) and service workers
      // behave differently there. `next start` is also what users actually get.
      command: "npm run build && npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
      env: { NEXT_TELEMETRY_DISABLED: "1" },
    },
  ],
});
