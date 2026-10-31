import { describe, expect, it } from "vitest";
import { dayBoundary, nextDays } from "./format";

describe("format helpers", () => {
  it("dayBoundary uses Kyiv offset (winter and summer)", () => {
    expect(dayBoundary("2026-11-03")).toBe("2026-11-03T00:00:00+02:00");
    expect(dayBoundary("2026-07-03")).toBe("2026-07-03T00:00:00+03:00");
    expect(dayBoundary("2026-10-25")).toBe("2026-10-25T00:00:00+03:00");
  });
  it("nextDays starts today in Kyiv", () => {
    const d = nextDays(7, "Europe/Kyiv", new Date("2026-10-31T22:30:00Z"));
    expect(d[0]).toBe("2026-11-01");
    expect(d).toHaveLength(7);
  });
});
