import { describe, expect, it } from "vitest";
import { computeStats, mondayOf } from "./stats";
import { emailAllowed } from "./allowed-email";

describe("computeStats", () => {
  const now = new Date("2026-10-02T12:00:00Z"); // a Friday
  it("handles empty input", () => {
    const s = computeStats([], now);
    expect(s.total).toBe(0);
    expect(s.responseRate).toBeNull();
    expect(s.appliedPerWeek).toHaveLength(8);
  });
  it("counts statuses and response rate", () => {
    const s = computeStats(
      [
        { status: "SAVED", appliedAt: null },
        { status: "APPLIED", appliedAt: new Date("2026-10-01T00:00:00Z") },
        { status: "OA", appliedAt: new Date("2026-09-20T00:00:00Z") },
        { status: "REJECTED", appliedAt: new Date("2026-09-21T00:00:00Z") },
      ],
      now,
    );
    expect(s.applied).toBe(3);
    expect(s.responseRate).toBeCloseTo(1 / 3);
    expect(s.appliedPerWeek.at(-1)).toEqual({ weekStart: "2026-09-28", count: 1 });
    expect(s.appliedPerWeek.find((w) => w.weekStart === "2026-09-14")?.count).toBe(1);
  });
  it("mondayOf", () => expect(mondayOf(new Date("2026-10-04T10:00:00Z")).toISOString().slice(0, 10)).toBe("2026-09-28"));
});

describe("emailAllowed", () => {
  it("allows all when unset", () => expect(emailAllowed("a@b.com", "")).toBe(true));
  it("restricts by domain", () => {
    expect(emailAllowed("a@live.concordia.ca", "live.concordia.ca, concordia.ca")).toBe(true);
    expect(emailAllowed("a@gmail.com", "live.concordia.ca")).toBe(false);
    expect(emailAllowed(null, "live.concordia.ca")).toBe(false);
  });
});
