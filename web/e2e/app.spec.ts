import { expect, test } from "@playwright/test";
import { PrismaClient } from "@prisma/client";
import { E2E_DB } from "../playwright.config";
import { login, saveJob } from "./helpers";

test("anonymous users are sent to the landing page", async ({ page }) => {
  await page.goto("/board");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
});

test("jobs list shows postings and search filters them", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("job-row")).toHaveCount(3);
  await page.getByPlaceholder("Search title or company…").fill("devops");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("job-row")).toHaveCount(1);
  await expect(page.getByText("Stagiaire DevOps")).toBeVisible();
});

test("save → board → move through stages → stats", async ({ page }) => {
  await login(page);
  await saveJob(page, "Software Engineer Intern");

  await page.goto("/board");
  const saved = page.getByTestId("col-SAVED");
  await expect(saved.getByTestId("card")).toHaveCount(1);

  const patched = page.waitForResponse((r) => r.url().includes("/api/applications/") && r.request().method() === "PATCH");
  await saved.getByLabel("Status").selectOption("APPLIED");
  await patched;
  await expect(page.getByTestId("col-APPLIED").getByTestId("card")).toHaveCount(1);

  await page.reload(); // persisted server-side
  await expect(page.getByTestId("col-APPLIED").getByTestId("card")).toHaveCount(1);

  const patchedOa = page.waitForResponse((r) => r.url().includes("/api/applications/") && r.request().method() === "PATCH");
  await page.getByTestId("col-APPLIED").getByLabel("Status").selectOption("OA");
  await patchedOa;
  await expect(page.getByTestId("col-OA").getByTestId("card")).toHaveCount(1);

  await page.goto("/stats");
  await expect(page.getByText("Response rate").locator("..")).toContainText("100%");
});

test("drag and drop moves a card between columns", async ({ page }) => {
  await login(page);
  await saveJob(page, "Stagiaire DevOps");
  await page.goto("/board");

  const handle = page.getByTestId("col-SAVED").getByLabel("Drag");
  const from = await handle.boundingBox();
  const to = await page.getByTestId("col-APPLIED").boundingBox();
  await page.mouse.move(from!.x + 5, from!.y + 5);
  await page.mouse.down();
  await page.mouse.move(to!.x + to!.width / 2, to!.y + 60, { steps: 15 });
  const patched = page.waitForResponse((r) => r.url().includes("/api/applications/") && r.request().method() === "PATCH");
  await page.mouse.up();
  await patched;

  await expect(page.getByTestId("col-APPLIED").getByTestId("card")).toHaveCount(1);
  await page.reload();
  await expect(page.getByTestId("col-APPLIED").getByTestId("card")).toHaveCount(1);
});

test("users only see their own board", async ({ page, browser }) => {
  await login(page);
  await saveJob(page, "Cybersecurity Intern");

  const other = await browser.newPage();
  await login(other);
  await other.goto("/board");
  await expect(other.getByTestId("card")).toHaveCount(0);
  await other.close();
});

test("reminders can be added and are emailed once when due", async ({ page }) => {
  const email = await login(page);
  await saveJob(page, "Software Engineer Intern");
  await page.goto("/board");

  const card = page.getByTestId("card");
  await card.getByLabel("Reminders").click();
  await card.getByLabel("Reminder date").fill("2020-01-01"); // already due
  await card.getByLabel("Reminder note").fill("follow up with recruiter");
  await card.getByRole("button", { name: "Add" }).click();
  await expect(card.getByText(/follow up with recruiter/)).toBeVisible();

  process.env.DATABASE_URL = E2E_DB;
  const { sweepReminders } = await import("../src/lib/reminders");
  const sent: { to: string; subject: string; body: string }[] = [];
  const mock = async (to: string, subject: string, body: string) => void sent.push({ to, subject, body });

  expect((await sweepReminders(new Date(), mock)).sent).toBeGreaterThanOrEqual(1);
  const mine = sent.filter((s) => s.to === email);
  expect(mine).toHaveLength(1);
  expect(mine[0].body).toContain("follow up with recruiter");

  expect((await sweepReminders(new Date(), mock)).sent).toBe(0); // not sent twice

  const db = new PrismaClient({ datasources: { db: { url: E2E_DB } } });
  expect(await db.reminder.count({ where: { sentAt: { not: null }, application: { user: { email } } } })).toBe(1);
  await db.$disconnect();
});

test("API rejects unauthenticated and cross-user access", async ({ request, page }) => {
  expect((await request.post("/api/applications", { data: { jobId: "x" } })).status()).toBe(401);

  await login(page);
  await saveJob(page, "Software Engineer Intern");
  await page.goto("/board");

  const db = new PrismaClient({ datasources: { db: { url: E2E_DB } } });
  const app = await db.application.findFirstOrThrow({ orderBy: { createdAt: "desc" } });
  await db.$disconnect();

  const other = await page.context().browser()!.newPage();
  await login(other);
  const res = await other.request.patch(`/api/applications/${app.id}`, { data: { status: "OFFER" } });
  expect(res.status()).toBe(404);
  await other.close();
});
