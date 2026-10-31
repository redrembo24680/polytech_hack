import { describe, expect, it } from "vitest";
import { addDays, weekDays, weekStart } from "./week";

describe("week helpers", () => {
  it("finds Monday", () => {
    expect(weekStart("2026-11-01")).toBe("2026-10-26"); // Sunday
    expect(weekStart("2026-11-02")).toBe("2026-11-02"); // Monday
  });
  it("adds days across month ends and lists the week", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(weekDays("2026-10-26")[6]).toBe("2026-11-01");
  });
});
