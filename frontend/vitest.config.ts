import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],   // e2e/ is Playwright's, not vitest's
    exclude: ["e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      include: ["app/lib/**"],
      reporter: ["text", "json-summary"],
      thresholds: { lines: 70, functions: 70 },
    },
  },
});
