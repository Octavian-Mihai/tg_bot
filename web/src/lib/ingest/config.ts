import { readFileSync } from "node:fs";
import path from "node:path";
import { parse } from "smol-toml";

export interface Company { name: string; ats: "greenhouse" | "lever"; slug: string }
export interface IngestConfig { locations: string[]; companies: Company[] }

/** Reads the same companies.toml the Python bot uses (repo root). */
export function loadConfig(file = process.env.COMPANIES_TOML ?? path.resolve(process.cwd(), "../companies.toml")): IngestConfig {
  const data = parse(readFileSync(file, "utf8")) as any;
  const companies: Company[] = (data.company ?? []).map((c: any) => {
    if (!c.name || !c.slug || !["greenhouse", "lever"].includes(c.ats)) throw new Error(`bad company entry: ${JSON.stringify(c)}`);
    return { name: c.name, ats: c.ats, slug: c.slug };
  });
  return { locations: data.locations?.length ? data.locations : ["montreal", "quebec", "qc"], companies };
}
