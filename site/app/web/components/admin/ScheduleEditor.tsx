"use client";

import { Input } from "@/components/ui/Input";
import { WEEKDAYS, validateDays, type DayState } from "@/lib/schedule";

export function ScheduleEditor({ value, onChange }: { value: DayState[]; onChange: (v: DayState[]) => void }) {
  const errors = validateDays(value);
  const set = (i: number, patch: Partial<DayState>) => onChange(value.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  return (
    <div className="space-y-1.5">
      {value.map((d, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <label className="flex w-16 items-center gap-2 text-sm font-medium text-slate-800">
            <input type="checkbox" checked={d.on} onChange={(e) => set(i, { on: e.target.checked })} aria-label={`Працює: ${WEEKDAYS[i]}`} />
            {WEEKDAYS[i]}
          </label>
          {d.on ? (
            <>
              <Input type="time" aria-label={`${WEEKDAYS[i]} з`} value={d.start} onChange={(e) => set(i, { start: e.target.value })} className="!w-28" />
              <span className="text-slate-400">–</span>
              <Input type="time" aria-label={`${WEEKDAYS[i]} до`} value={d.end} onChange={(e) => set(i, { end: e.target.value })} className="!w-28" />
              {errors[i] && <span className="text-xs text-red-600">{errors[i]}</span>}
            </>
          ) : (
            <span className="text-sm text-slate-400">вихідний</span>
          )}
        </div>
      ))}
    </div>
  );
}
