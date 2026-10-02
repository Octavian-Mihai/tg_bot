import { execSync } from "node:child_process";
import { PrismaClient } from "@prisma/client";
import { E2E_DB } from "../playwright.config";

export default async function globalSetup() {
  process.env.DATABASE_URL = E2E_DB;
  execSync("npx prisma db push --skip-generate --accept-data-loss", { stdio: "ignore", env: { ...process.env, DATABASE_URL: E2E_DB } });
  const db = new PrismaClient({ datasources: { db: { url: E2E_DB } } });
  await db.reminder.deleteMany();
  await db.application.deleteMany();
  await db.job.deleteMany();
  await db.user.deleteMany();
  const jobs = [
    ["Software Engineer Intern", "Acme"],
    ["Stagiaire DevOps", "Globex"],
    ["Cybersecurity Intern", "Initech"],
  ];
  for (const [i, [title, company]] of jobs.entries()) {
    await db.job.create({
      data: { source: "test", externalId: `test:${i}`, dedupeKey: `${company}|${title}`.toLowerCase(), title, company, location: "Montreal", url: `https://example.com/${i}` },
    });
  }
  await db.$disconnect();
}
