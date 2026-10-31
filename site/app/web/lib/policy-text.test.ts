import { describe, expect, it } from "vitest";
import { policyToText } from "./policy-text";
import type { Policy } from "./types";

const perms: Policy["agent_permissions"] = {
  reschedule: "auto",
  cancel: "auto",
  refund: "approval",
  refund_auto_limit: 0,
  goodwill_exception: "forbidden",
  goodwill_per_client_per_180d: 0,
  goodwill_requires_zero_no_shows: true,
  waive_no_show_fee: "forbidden",
};

const lumen: Policy = {
  cancellation_window_hours: 24,
  late_change_forfeits_prepayment: true,
  no_show_fee: 300,
  prepayment_required: true,
  agent_permissions: perms,
};

describe("policyToText", () => {
  it("lumen: 24 год, 300 грн, передоплата, in order", () => {
    expect(policyToText(lumen)).toEqual([
      "Скасування або перенесення пізніше ніж за 24 год — передоплата не повертається",
      "Неявка — штраф 300 грн",
      "Потрібна передоплата",
    ]);
  });

  it("dentaplus-like: 48 год, 500 грн", () => {
    const text = policyToText({ ...lumen, cancellation_window_hours: 48, no_show_fee: 500 }).join("|");
    expect(text).toContain("48 год");
    expect(text).toContain("500 грн");
  });

  it("free cancellation, no fee, no prepayment", () => {
    expect(
      policyToText({
        ...lumen,
        late_change_forfeits_prepayment: false,
        no_show_fee: 0,
        prepayment_required: false,
      }),
    ).toEqual(["Безкоштовне скасування або перенесення не пізніше ніж за 24 год"]);
  });

  it("never mentions agent permissions", () => {
    expect(policyToText(lumen).join(" ")).not.toMatch(/agent|refund|goodwill/i);
  });
});
