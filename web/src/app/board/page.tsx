import { db } from "@/lib/db";
import { requireUser } from "@/lib/session";
import { Board, type CardData } from "@/components/Board";

export const dynamic = "force-dynamic";

export default async function BoardPage() {
  const user = await requireUser();
  const apps = await db.application.findMany({
    where: { userId: user.id },
    include: { job: true, reminders: { where: { sentAt: null }, orderBy: { dueAt: "asc" } } },
    orderBy: { position: "asc" },
  });
  const cards: CardData[] = apps.map((a) => ({
    id: a.id,
    status: a.status,
    position: a.position,
    title: a.job.title,
    company: a.job.company,
    url: a.job.url,
    reminders: a.reminders.map((r) => ({ id: r.id, dueAt: r.dueAt.toISOString(), note: r.note })),
  }));
  return <Board initial={cards} />;
}
