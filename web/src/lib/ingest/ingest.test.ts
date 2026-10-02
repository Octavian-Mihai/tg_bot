import { describe, expect, it } from "vitest";
import { filterInternships } from "./filters";
import { normalizeAdzuna, normalizeGreenhouse, normalizeLever } from "./sources";
import { dedupeBatch } from "./run";
import { dedupeKey, locationMatcher, normalizeText } from "./text";
import type { RawJob } from "./types";

const job = (o: Partial<RawJob>): RawJob => ({ id: "x:1", title: "Software Intern", company: "Acme", location: "Montreal", url: "u", source: "x", ...o });

describe("text", () => {
  it("strips accents", () => expect(normalizeText("Montréal")).toBe("montreal"));
  it("matches whole-word locations", () => {
    const m = locationMatcher(["montreal", "qc"]);
    expect(m("Montréal, QC")).toBe(true);
    expect(m("Aqcity")).toBe(false);
  });
  it("builds a cross-source key", () => expect(dedupeKey({ company: "Épic ", title: " Intern" })).toBe("epic|intern"));
});

describe("filters", () => {
  it("keeps tech internships only", () => {
    const kept = filterInternships([
      job({ title: "Software Engineer Intern" }),
      job({ title: "Stagiaire en informatique" }),
      job({ title: "Senior Software Engineer" }),
      job({ title: "Marketing Intern" }),
    ]);
    expect(kept.map((j) => j.title)).toEqual(["Software Engineer Intern", "Stagiaire en informatique"]);
  });
});

describe("normalizers", () => {
  it("greenhouse", () =>
    expect(normalizeGreenhouse({ id: 5, title: " X ", location: { name: "Montreal" }, absolute_url: "u" }, "s", "C").id).toBe("greenhouse:s:5"));
  it("lever", () =>
    expect(normalizeLever({ id: "a", text: "T", categories: { location: "L" }, hostedUrl: "u" }, "s", "C").source).toBe("lever"));
  it("adzuna strips tags and defaults company", () => {
    const j = normalizeAdzuna({ id: 1, title: "<b>Dev</b> Intern", redirect_url: "u" });
    expect(j.title).toBe("Dev Intern");
    expect(j.company).toBe("Unknown company");
  });
  it("throws on malformed", () => expect(() => normalizeLever({}, "s", "C")).toThrow());
});

describe("dedupeBatch", () => {
  it("drops same posting from another source, keeps first", () => {
    const out = dedupeBatch([job({ id: "gh:1", source: "greenhouse" }), job({ id: "adzuna:9", source: "adzuna" })]);
    expect(out.map((j) => j.id)).toEqual(["gh:1"]);
  });
  it("keeps same-titled postings from one source", () => {
    const out = dedupeBatch([job({ id: "gh:1", source: "greenhouse" }), job({ id: "gh:2", source: "greenhouse" })]);
    expect(out).toHaveLength(2);
  });
});
