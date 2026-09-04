import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 20000,
  use: {
    baseURL: "http://localhost:5173",
    video: "retain-on-failure",
  },
  // Assumes `npm run dev` (frontend) and the backend are already running --
  // deliberately not auto-starting either here, since the backend needs a
  // seeded DB + trained models first (see README.md), which this config
  // has no business doing on every test run.
});
