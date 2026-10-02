import "dotenv/config";
import { PgBoss } from "pg-boss";
import { runIngest } from "../src/lib/ingest/run";
import { sweepReminders } from "../src/lib/reminders";

const INGEST = "ingest-jobs";
const REMINDERS = "send-reminders";

async function main() {
  const boss = new PgBoss(process.env.DATABASE_URL!);
  boss.on("error", (e) => console.error("pg-boss error:", e));
  await boss.start();

  await boss.createQueue(INGEST, { retryLimit: 2, retryDelay: 60 });
  await boss.createQueue(REMINDERS, { retryLimit: 1, retryDelay: 30 });

  await boss.work(INGEST, async () => {
    await runIngest();
  });
  await boss.work(REMINDERS, async () => {
    const r = await sweepReminders();
    if (r.sent || r.failed) console.log(`reminders: ${r.sent} sent, ${r.failed} failed`);
  });

  await boss.schedule(INGEST, "0 */6 * * *"); // every 6h
  await boss.schedule(REMINDERS, "*/5 * * * *"); // every 5 min
  await boss.send(INGEST); // fetch once on boot so a fresh deploy isn't empty

  console.log("worker running: ingest every 6h, reminders every 5m");
  const stop = async () => { await boss.stop({ graceful: true }); process.exit(0); };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
}

main().catch((e) => { console.error(e); process.exit(1); });
