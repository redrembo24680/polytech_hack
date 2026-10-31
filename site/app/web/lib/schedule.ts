import type { ScheduleRow } from "./types";

/** Backend weekday: 0 = Monday (Python convention). */
export const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"] as const;

export interface DayState {
  on: boolean;
  start: string;
  end: string;
}

export function rowsToDays(rows: ScheduleRow[]): DayState[] {
  return WEEKDAYS.map((_, i) => {
    const r = rows.find((x) => x.weekday === i);
    return r ? { on: true, start: r.start.slice(0, 5), end: r.end.slice(0, 5) } : { on: false, start: "10:00", end: "19:00" };
  });
}

export function daysToRows(days: DayState[]): ScheduleRow[] {
  return days.flatMap((d, i) => (d.on ? [{ weekday: i, start: d.start, end: d.end }] : []));
}

/** Per-weekday error text (or null). Only enabled days are validated. */
export function validateDays(days: DayState[]): (string | null)[] {
  return days.map((d) => {
    if (!d.on) return null;
    if (!d.start || !d.end) return "Вкажіть час";
    return d.start < d.end ? null : "Початок має бути раніше за кінець";
  });
}
