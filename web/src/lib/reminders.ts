import { db } from "./db";
import { sendEmail } from "./email";

/** Email every due, unsent reminder and mark it sent. A failed send stays unsent and is retried next sweep. */
export async function sweepReminders(now = new Date(), send = sendEmail): Promise<{ sent: number; failed: number }> {
  const due = await db.reminder.findMany({
    where: { sentAt: null, dueAt: { lte: now } },
    include: { application: { include: { job: true, user: true } } },
  });
  let sent = 0, failed = 0;
  for (const r of due) {
    const { job, user } = r.application;
    const base = process.env.APP_URL ?? "http://localhost:3000";
    try {
      await send(
        user.email,
        `Reminder: ${job.title} at ${job.company}`,
        `${r.note || "Time to follow up."}\n\n${job.title} — ${job.company}\nStatus: ${r.application.status}\n${job.url}\n\nYour board: ${base}/board`,
      );
      await db.reminder.update({ where: { id: r.id }, data: { sentAt: new Date() } });
      sent++;
    } catch (e) {
      console.error(`reminder ${r.id} failed:`, (e as Error).message);
      failed++;
    }
  }
  return { sent, failed };
}
