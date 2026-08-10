import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://localhost:3000",
  },
  webServer: [
    {
      command: "cd .. && python -m uvicorn backend.app:app --port 8000",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],
});
