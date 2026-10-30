import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run the built app against the real backend in demo mode (canned AI
// responses, no API keys), each server with a throwaway data folder:
//  - first-run: an empty app, the first-time setup with a file to upload (smoke.spec.ts)
//  - demo-tour: the demo as `launch.bat --demo` starts it, seeded with the example (tour.spec.ts)
const FIRST_RUN_PORT = 8790
const TOUR_PORT = 8791

function server(port: number, name: string, env: Record<string, string>) {
  return {
    // Start from an empty data folder every run.
    command: `node -e "require('fs').rmSync('../data/${name}', { recursive: true, force: true })" && uv run --project ../backend proseferno --demo --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { PROSEFERNO_DATA_DIR: `../data/${name}`, PROSEFERNO_SEED_SAMPLES_DIR: `../data/${name}/__no_seed__`, ...env },
  }
}

const desktop = { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } }

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    trace: 'retain-on-failure',
    // Set PW_CHANNEL=msedge (or chrome) to use an installed browser instead of downloading Chromium.
    channel: process.env.PW_CHANNEL || undefined,
  },
  projects: [
    { name: 'first-run', testMatch: 'smoke.spec.ts', use: { ...desktop, baseURL: `http://127.0.0.1:${FIRST_RUN_PORT}` } },
    { name: 'demo-tour', testMatch: 'tour.spec.ts', use: { ...desktop, baseURL: `http://127.0.0.1:${TOUR_PORT}` } },
  ],
  webServer: [server(FIRST_RUN_PORT, 'e2e', { PROSEFERNO_DEMO_SEED: 'false' }), server(TOUR_PORT, 'e2e-tour', {})],
})
