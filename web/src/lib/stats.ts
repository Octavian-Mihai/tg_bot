export const STATUSES = ["SAVED", "APPLIED", "OA", "INTERVIEW", "OFFER", "REJECTED"] as const;
export type StatusName = (typeof STATUSES)[number];

export interface StatsInput { status: StatusName; appliedAt: Date | null }

export interface Stats {
  total: number;
  byStatus: Record<StatusName, number>;
  applied: number; // everything that left SAVED
  responseRate: number | null; // share of applications that reached OA or later (excl. rejected-with-no-response is unknowable, so rejected counts as applied only)
  appliedPerWeek: { weekStart: string; count: number }[];
}

export function mondayOf(d: Date): Date {
  const x = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  x.setUTCDate(x.getUTCDate() - ((x.getUTCDay() + 6) % 7));
  return x;
}

export function computeStats(apps: StatsInput[], now = new Date(), weeks = 8): Stats {
  const byStatus = Object.fromEntries(STATUSES.map((s) => [s, 0])) as Record<StatusName, number>;
  for (const a of apps) byStatus[a.status]++;

  const applied = apps.length - byStatus.SAVED;
  const progressed = byStatus.OA + byStatus.INTERVIEW + byStatus.OFFER;

  const thisWeek = mondayOf(now);
  const buckets = new Map<string, number>();
  for (let i = weeks - 1; i >= 0; i--) {
    const d = new Date(thisWeek);
    d.setUTCDate(d.getUTCDate() - i * 7);
    buckets.set(d.toISOString().slice(0, 10), 0);
  }
  for (const a of apps) {
    if (!a.appliedAt) continue;
    const key = mondayOf(a.appliedAt).toISOString().slice(0, 10);
    if (buckets.has(key)) buckets.set(key, buckets.get(key)! + 1);
  }

  return {
    total: apps.length,
    byStatus,
    applied,
    responseRate: applied > 0 ? progressed / applied : null,
    appliedPerWeek: [...buckets].map(([weekStart, count]) => ({ weekStart, count })),
  };
}
