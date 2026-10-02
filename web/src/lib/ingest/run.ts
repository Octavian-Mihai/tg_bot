import { db } from "../db";
import { loadConfig } from "./config";
import { filterInternships } from "./filters";
import { fetchAdzuna, fetchGreenhouse, fetchLever } from "./sources";
import { dedupeKey } from "./text";
import type { RawJob } from "./types";

/** Drop duplicates inside one batch; earlier entries win (company boards are collected before Adzuna). */
export function dedupeBatch(jobs: RawJob[]): RawJob[] {
  const ids = new Set<string>();
  const keys = new Map<string, string>(); // dedupeKey -> source
  const out: RawJob[] = [];
  for (const j of jobs) {
    const k = dedupeKey(j);
    const seenSource = keys.get(k);
    if (ids.has(j.id) || (seenSource && seenSource !== j.source)) continue;
    ids.add(j.id);
    keys.set(k, j.source);
    out.push(j);
  }
  return out;
}

export interface IngestResult { fetched: number; kept: number; created: number; sourcesOk: number; sourcesFailed: number }

export async function runIngest(log: (m: string) => void = console.log): Promise<IngestResult> {
  const config = loadConfig();
  const jobs: RawJob[] = [];
  let ok = 0, failed = 0;

  for (const c of config.companies) {
    try {
      jobs.push(...(await (c.ats === "greenhouse" ? fetchGreenhouse : fetchLever)(c.slug, c.name, config.locations)));
      ok++;
    } catch (e) {
      log(`source ${c.ats}/${c.slug} failed: ${(e as Error).message}`);
      failed++;
    }
  }
  const { ADZUNA_APP_ID: id, ADZUNA_APP_KEY: key } = process.env;
  if (id && key) {
    try {
      jobs.push(...(await fetchAdzuna(id, key)));
      ok++;
    } catch (e) {
      log(`source adzuna failed: ${(e as Error).message}`);
      failed++;
    }
  } else log("adzuna skipped (ADZUNA_APP_ID/KEY not set)");

  if (ok === 0) throw new Error("every source failed");

  const kept = dedupeBatch(filterInternships(jobs));
  let created = 0;
  for (const j of kept) {
    const key = dedupeKey(j);
    // The same posting on another source (same company+title) is already stored under dedupeKey.
    const existing = await db.job.findFirst({ where: { OR: [{ externalId: j.id }, { dedupeKey: key }] } });
    if (existing) {
      await db.job.update({ where: { id: existing.id }, data: { lastSeenAt: new Date() } });
      continue;
    }
    await db.job.create({
      data: { source: j.source, externalId: j.id, dedupeKey: key, title: j.title, company: j.company, location: j.location, url: j.url },
    });
    created++;
  }
  log(`ingest: ${jobs.length} fetched, ${kept.length} after filter, ${created} new (${ok} sources ok, ${failed} failed)`);
  return { fetched: jobs.length, kept: kept.length, created, sourcesOk: ok, sourcesFailed: failed };
}
