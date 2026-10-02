import type { RawJob } from "./types";

/** Lowercase and strip accents so "Montréal" and "montreal" compare equal. */
export function normalizeText(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Cross-source identity: the same posting on Adzuna and a company board shares it. */
export function dedupeKey(job: Pick<RawJob, "company" | "title">): string {
  return `${normalizeText(job.company).trim()}|${normalizeText(job.title).trim()}`;
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function locationMatcher(keywords: string[]) {
  const re = new RegExp(`\\b(${keywords.map((k) => esc(normalizeText(k))).join("|")})\\b`);
  return (text: string) => re.test(normalizeText(text || ""));
}
