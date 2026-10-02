import { db } from "@/lib/db";
import { requireUser } from "@/lib/session";
import { STATUSES, computeStats } from "@/lib/stats";

export const dynamic = "force-dynamic";

export default async function StatsPage() {
  const user = await requireUser();
  const apps = await db.application.findMany({ where: { userId: user.id }, select: { status: true, appliedAt: true } });
  const s = computeStats(apps);
  const maxWeek = Math.max(1, ...s.appliedPerWeek.map((w) => w.count));

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="Tracked" value={s.total} />
        <Tile label="Applied" value={s.applied} />
        <Tile label="Interviews" value={s.byStatus.INTERVIEW} />
        <Tile label="Response rate" value={s.responseRate === null ? "—" : `${Math.round(s.responseRate * 100)}%`} />
      </div>

      <section>
        <h2 className="mb-2 font-semibold">By stage</h2>
        <ul className="space-y-1">
          {STATUSES.map((st) => (
            <li key={st} className="flex items-center gap-2 text-sm">
              <span className="w-20">{st}</span>
              <div className="h-4 flex-1 rounded bg-slate-200">
                <div className="h-4 rounded bg-slate-700" style={{ width: `${s.total ? (s.byStatus[st] / s.total) * 100 : 0}%` }} />
              </div>
              <span className="w-6 text-right">{s.byStatus[st]}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Applications per week</h2>
        <div className="flex h-32 items-end gap-2">
          {s.appliedPerWeek.map((w) => (
            <div key={w.weekStart} className="flex flex-1 flex-col items-center gap-1 text-xs">
              <span>{w.count}</span>
              <div className="w-full rounded-t bg-slate-700" style={{ height: `${(w.count / maxWeek) * 100}%`, minHeight: 2 }} />
              <span className="text-slate-500">{w.weekStart.slice(5)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border bg-white p-4">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  );
}
