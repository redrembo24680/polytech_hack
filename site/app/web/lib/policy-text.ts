import type { Policy } from "./types";

/** Human-readable (Ukrainian) cancellation rules for customers. Never exposes agent_permissions. */
export function policyToText(policy: Policy): string[] {
  const h = policy.cancellation_window_hours;
  const lines: string[] = [];
  lines.push(
    policy.late_change_forfeits_prepayment
      ? `Скасування або перенесення пізніше ніж за ${h} год — передоплата не повертається`
      : `Безкоштовне скасування або перенесення не пізніше ніж за ${h} год`,
  );
  if (policy.no_show_fee > 0) lines.push(`Неявка — штраф ${policy.no_show_fee} грн`);
  if (policy.prepayment_required) lines.push("Потрібна передоплата");
  return lines;
}
