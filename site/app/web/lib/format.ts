export const formatPrice = (n: number) => `${n} грн`;
export const formatDuration = (min: number) => `${min} хв`;

const TZ = "Europe/Kyiv";

export function formatDateTime(iso: string, tz = TZ): string {
  const d = new Date(iso);
  const date = new Intl.DateTimeFormat("uk-UA", { weekday: "long", day: "numeric", month: "long", timeZone: tz }).format(d);
  return `${date}, ${formatTime(iso, tz)}`;
}
export function formatTime(iso: string, tz = TZ): string {
  return new Intl.DateTimeFormat("uk-UA", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: tz }).format(new Date(iso));
}

/** "YYYY-MM-DD" of an instant in the given tz. */
export function dateKey(d: Date, tz = TZ): string {
  return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: tz }).format(d);
}

/** UTC offset in minutes of tz at the instant d. */
function offsetMinutes(d: Date, tz: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(d);
  const g = (t: string) => Number(parts.find((p) => p.type === t)!.value);
  const asUtc = Date.UTC(g("year"), g("month") - 1, g("day"), g("hour"), g("minute"), g("second"));
  return Math.round((asUtc - Math.floor(d.getTime() / 1000) * 1000) / 60000);
}

/** ISO string with offset for local midnight of "YYYY-MM-DD" in tz. */
export function dayBoundary(key: string, tz = TZ): string {
  const [y, m, d] = key.split("-").map(Number);
  const guess = new Date(Date.UTC(y, m - 1, d));
  let off = offsetMinutes(guess, tz);
  off = offsetMinutes(new Date(guess.getTime() - off * 60000), tz);
  const sign = off >= 0 ? "+" : "-";
  const a = Math.abs(off);
  const hh = String(Math.floor(a / 60)).padStart(2, "0");
  const mm = String(a % 60).padStart(2, "0");
  return `${key}T00:00:00${sign}${hh}:${mm}`;
}

/** 7 consecutive date keys starting today in tz. */
export function nextDays(count = 7, tz = TZ, now = new Date()): string[] {
  const [y, m, d] = dateKey(now, tz).split("-").map(Number);
  return Array.from({ length: count }, (_, i) => new Date(Date.UTC(y, m - 1, d + i)).toISOString().slice(0, 10));
}

export function dayLabel(key: string): { weekday: string; day: string } {
  const [y, m, d] = key.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d, 12));
  return {
    weekday: new Intl.DateTimeFormat("uk-UA", { weekday: "short", timeZone: "UTC" }).format(dt),
    day: new Intl.DateTimeFormat("uk-UA", { day: "numeric", month: "short", timeZone: "UTC" }).format(dt),
  };
}
