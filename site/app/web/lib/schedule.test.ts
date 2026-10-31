import { describe, expect, it } from "vitest";
import { daysToRows, rowsToDays, validateDays } from "./schedule";

describe("schedule", () => {
  it("round-trips rows", () => {
    const rows = [{ weekday: 0, start: "12:00", end: "14:00" }];
    const days = rowsToDays(rows);
    expect(days[0].on).toBe(true);
    expect(days[1].on).toBe(false);
    expect(daysToRows(days)).toEqual(rows);
  });
  it("validates start<end for enabled days only", () => {
    const days = rowsToDays([{ weekday: 2, start: "15:00", end: "14:00" }]);
    expect(validateDays(days)[2]).not.toBeNull();
    expect(validateDays(days)[0]).toBeNull();
  });
});
