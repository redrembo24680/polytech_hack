import type { BookingEvent } from "@/lib/types";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { EVENT_LABEL, byLabel } from "./status";

/** History, newest first. Events by the AI agent are highlighted and badged. */
export function Timeline({ history }: { history: BookingEvent[] }) {
  const events = history.map((e, i) => ({ e, i })).reverse();
  if (events.length === 0) return <p className="text-sm text-slate-500">Подій ще немає.</p>;
  return (
    <ol className="space-y-2">
      {events.map(({ e, i }) => {
        const ai = e.by === "agent";
        return (
          <li
            key={i}
            className={cn(
              "rounded-lg border px-3 py-2 text-sm",
              ai ? "border-accent-200 bg-accent-50" : "border-slate-200 bg-white",
            )}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-slate-900">{EVENT_LABEL[e.event] ?? e.event}</span>
              {ai && <Badge color="accent">AI</Badge>}
              <span className="text-slate-500">{byLabel(e.by)}</span>
              <span className="ml-auto text-xs text-slate-500">{formatDateTime(e.ts)}</span>
            </div>
            {e.note && <p className="mt-1 text-slate-600">{e.note}</p>}
          </li>
        );
      })}
    </ol>
  );
}
