import { defineConfig, devices } from '@playwright/test'

// End-to-end smoke test: runs the built app against the real backend in demo mode
// (canned AI responses, no API keys) with a throwaway data folder.
const PORT = 8790

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    // Set PW_CHANNEL=msedge (or chrome) to use an installed browser instead of downloading Chromium.
    channel: process.env.PW_CHANNEL || undefined,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } }],
  webServer: {
    // Start from an empty data folder every run.
    command: `node -e "require('fs').rmSync('../data/e2e', { recursive: true, force: true })" && uv run --project ../backend proseferno --demo --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      PROSEFERNO_DATA_DIR: '../data/e2e',
      PROSEFERNO_SEED_SAMPLES_DIR: '../examples/__none__',
    },
  },
})
