import { defineConfig } from "@playwright/test";

export const E2E_DB = process.env.E2E_DATABASE_URL ?? "postgresql://internbot:internbot@localhost:5433/internbot_e2e";
const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  webServer: {
    command: `npx next dev -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      DATABASE_URL: E2E_DB,
      AUTH_SECRET: "e2e-secret",
      AUTH_DEV_LOGIN: "1",
      AUTH_URL: `http://localhost:${PORT}`,
      APP_URL: `http://localhost:${PORT}`,
      ALLOWED_EMAIL_DOMAINS: "",
      NODE_ENV: "development",
    },
  },
});
