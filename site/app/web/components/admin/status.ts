import type { Booking, BookingStatus } from "@/lib/types";
import type { BadgeColor } from "@/components/ui/Badge";

export const STATUS_LABEL: Record<BookingStatus, string> = {
  scheduled: "Заплановано",
  completed: "Виконано",
  cancelled: "Скасовано",
  no_show: "Не прийшов",
};

export const STATUS_BADGE: Record<BookingStatus, BadgeColor> = {
  scheduled: "blue",
  completed: "green",
  cancelled: "gray",
  no_show: "red",
};

export const STATUS_CHIP: Record<BookingStatus, string> = {
  scheduled: "border-blue-200 bg-blue-50 text-blue-900",
  completed: "border-green-200 bg-green-50 text-green-900",
  cancelled: "border-slate-200 bg-slate-100 text-slate-500 line-through",
  no_show: "border-red-200 bg-red-50 text-red-900",
};

export const PREPAYMENT_LABEL: Record<string, string> = {
  held: "утримується",
  refunded: "повернено",
  forfeited: "втрачено",
  none: "немає",
};

export const FEE_LABEL: Record<string, string> = {
  charged: "стягнуто",
  waived: "знято",
  none: "немає",
};

export const EVENT_LABEL: Record<string, string> = {
  created: "Створено",
  prepayment_held: "Передоплату утримано",
  rescheduled: "Перенесено",
  cancelled: "Скасовано",
  completed: "Виконано",
  no_show: "Не прийшов",
  refunded: "Передоплату повернено",
  prepayment_refunded: "Передоплату повернено",
  prepayment_forfeited: "Передоплату втрачено",
  no_show_fee_charged: "Штраф нараховано",
  no_show_fee_waived: "Штраф знято",
  goodwill: "Виняток з доброї волі",
};

export function byLabel(by: string): string {
  if (by === "agent") return "AI-агент";
  if (by === "human:admin") return "Адміністратор";
  return by.startsWith("human:") ? by.slice(6) : by;
}

/** True when the most recent history event was made by the AI agent. */
export function lastByAgent(b: Booking): boolean {
  const h = b.history;
  return h.length > 0 && h[h.length - 1].by === "agent";
}
