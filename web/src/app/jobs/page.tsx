import { db } from "@/lib/db";
import { requireUser } from "@/lib/session";
import { SaveButton } from "@/components/SaveButton";

export const dynamic = "force-dynamic";

export default async function JobsPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const user = await requireUser();
  const { q } = await searchParams;
  const term = q?.trim();

  const jobs = await db.job.findMany({
    where: term
      ? { OR: [{ title: { contains: term, mode: "insensitive" } }, { company: { contains: term, mode: "insensitive" } }] }
      : undefined,
    orderBy: { firstSeenAt: "desc" },
    take: 200,
  });
  const saved = new Set(
    (await db.application.findMany({ where: { userId: user.id, jobId: { in: jobs.map((j) => j.id) } }, select: { jobId: true } })).map((a) => a.jobId),
  );

  return (
    <div className="space-y-4">
      <form className="flex gap-2">
        <input name="q" defaultValue={term} placeholder="Search title or company…" className="w-full max-w-sm rounded border px-3 py-1.5" />
        <button className="rounded border px-3 py-1.5 hover:bg-slate-100">Search</button>
      </form>
      <p className="text-sm text-slate-500">{jobs.length} postings</p>
      <ul className="divide-y rounded border bg-white">
        {jobs.map((j) => (
          <li key={j.id} className="flex items-center gap-4 p-3" data-testid="job-row">
            <div className="min-w-0 flex-1">
              <a href={j.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{j.title}</a>
              <div className="text-sm text-slate-600">
                {j.company} · {j.location || "—"} · <span className="text-slate-400">{j.source}</span>
              </div>
            </div>
            <SaveButton jobId={j.id} initiallySaved={saved.has(j.id)} />
          </li>
        ))}
        {jobs.length === 0 && <li className="p-6 text-center text-slate-500">No postings yet — the worker will fetch some soon.</li>}
      </ul>
    </div>
  );
}
