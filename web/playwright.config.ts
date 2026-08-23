import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "uv run uvicorn quality_case_agent.entrypoints.api.app:app --host 127.0.0.1 --port 8001",
      cwd: "..",
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174",
      url: "http://127.0.0.1:5174",
      env: { VITE_API_BASE: "http://127.0.0.1:8001/api/v1" },
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
