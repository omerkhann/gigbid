import { defineConfig, devices } from "@playwright/test";

// The e2e backend (apps/api/e2e_server.py) is the real API on in-process GigSim + MCP servers with a
// scripted LLM, so these tests are fast and repeatable. It needs Postgres (docker compose).
// Relative to the repo root (the e2e server command runs there).
const python = process.env.PYTHON ?? (process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  // CI (Linux): Playwright's own Chromium. Windows dev: the preinstalled Edge (Chromium-based), because
  // Playwright's Chromium download stalls there (antivirus locks chrome.dll mid-extraction).
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    channel: process.env.PW_CHANNEL ?? (process.platform === "win32" && !process.env.CI ? "msedge" : "chromium"),
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] }, testIgnore: /mobile.spec.ts/ },
    { name: "phone", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: `${python} -m apps.api.e2e_server --port 8000`,
      cwd: "../..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Production build, not next dev: dev compiles each route on first visit, which is slower than test timeouts.
      command: process.env.CI ? "npm run start" : "npm run build && npm run start",
      url: "http://localhost:3000/login",
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
    },
  ],
});
