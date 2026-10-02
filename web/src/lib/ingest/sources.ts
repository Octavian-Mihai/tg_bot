import type { RawJob } from "./types";
import { getJson, SourceError } from "./http";
import { locationMatcher } from "./text";

type Obj = Record<string, any>;

export function normalizeGreenhouse(raw: Obj, slug: string, company: string): RawJob {
  if (raw.id == null || !raw.absolute_url) throw new SourceError("malformed greenhouse job");
  return {
    id: `greenhouse:${slug}:${raw.id}`,
    title: String(raw.title ?? "").trim(),
    company,
    location: String(raw.location?.name ?? "").trim(),
    url: raw.absolute_url,
    source: "greenhouse",
  };
}

export async function fetchGreenhouse(slug: string, company: string, locations: string[]): Promise<RawJob[]> {
  const data = (await getJson(`https://boards-api.greenhouse.io/v1/boards/${slug}/jobs`)) as Obj;
  const inArea = locationMatcher(locations);
  const out: RawJob[] = [];
  for (const raw of data.jobs ?? []) {
    try {
      const job = normalizeGreenhouse(raw, slug, company);
      if (inArea(job.location)) out.push(job);
    } catch {
      /* skip malformed */
    }
  }
  return out;
}

export function normalizeLever(raw: Obj, slug: string, company: string): RawJob {
  if (!raw.id || !raw.hostedUrl) throw new SourceError("malformed lever posting");
  return {
    id: `lever:${slug}:${raw.id}`,
    title: String(raw.text ?? "").trim(),
    company,
    location: String(raw.categories?.location ?? "").trim(),
    url: raw.hostedUrl,
    source: "lever",
  };
}

export async function fetchLever(slug: string, company: string, locations: string[]): Promise<RawJob[]> {
  const data = await getJson(`https://api.lever.co/v0/postings/${slug}?mode=json`);
  if (!Array.isArray(data)) throw new SourceError("unexpected Lever response shape");
  const inArea = locationMatcher(locations);
  const out: RawJob[] = [];
  for (const raw of data as Obj[]) {
    try {
      const job = normalizeLever(raw, slug, company);
      const locs: string[] = [...(raw.categories?.allLocations ?? [])];
      if (raw.categories?.location) locs.push(raw.categories.location);
      if (locs.some(inArea)) out.push(job);
    } catch {
      /* skip malformed */
    }
  }
  return out;
}

const ADZUNA_KEYWORDS = [
  "software intern",
  "stagiaire développeur",
  "co-op software",
  "stagiaire informatique",
  "stagiaire",
  "stage informatique",
];

export function normalizeAdzuna(raw: Obj): RawJob {
  if (raw.id == null || !raw.redirect_url) throw new SourceError("malformed adzuna result");
  return {
    id: `adzuna:${raw.id}`,
    title: String(raw.title ?? "").replace(/<[^>]+>/g, "").trim(),
    company: String(raw.company?.display_name ?? "Unknown company").trim(),
    location: String(raw.location?.display_name ?? "").trim(),
    url: raw.redirect_url,
    source: "adzuna",
  };
}

export async function fetchAdzuna(appId: string, appKey: string, where = "Montreal, Quebec"): Promise<RawJob[]> {
  const jobs = new Map<string, RawJob>();
  for (const what of ADZUNA_KEYWORDS) {
    const qs = new URLSearchParams({
      app_id: appId,
      app_key: appKey,
      what,
      where,
      distance: "30",
      max_days_old: "30",
      results_per_page: "50",
      sort_by: "date",
      "content-type": "application/json",
    });
    const data = (await getJson(`https://api.adzuna.com/v1/api/jobs/ca/search/1?${qs}`)) as Obj;
    for (const raw of data.results ?? []) {
      try {
        const job = normalizeAdzuna(raw);
        if (!jobs.has(job.id)) jobs.set(job.id, job);
      } catch {
        /* skip malformed */
      }
    }
  }
  return [...jobs.values()];
}
