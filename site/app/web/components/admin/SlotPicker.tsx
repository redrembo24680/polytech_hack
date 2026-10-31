"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import type { Slot } from "@/lib/types";
import { cn } from "@/lib/cn";
import { dayBoundary, dayLabel, formatTime, nextDays } from "@/lib/format";
import { addDays } from "@/lib/week";

export interface SlotPickerProps {
  tenant: string;
  serviceId: string | null;
  staffId?: string;
  value: Slot | null;
  onChange: (slot: Slot | null) => void;
}

const DAYS = nextDays(14);

/** Day strip + slots list from GET /slots for one service. */
export function SlotPicker({ tenant, serviceId, staffId, value, onChange }: SlotPickerProps) {
  const [day, setDay] = useState(DAYS[0]);
  const path = serviceId
    ? `/api/tenants/${tenant}/slots?service_id=${serviceId}&from=${encodeURIComponent(dayBoundary(day))}&to=${encodeURIComponent(dayBoundary(addDays(day, 1)))}${staffId ? `&staff_id=${staffId}` : ""}`
    : null;
  const { data, isLoading } = useApi<Slot[]>(path);

  return (
    <div className="space-y-2">
      <div className="flex gap-1 overflow-x-auto pb-1">
        {DAYS.map((d) => {
          const l = dayLabel(d);
          return (
            <button
              key={d}
              type="button"
              onClick={() => {
                setDay(d);
                onChange(null);
              }}
              className={cn(
                "shrink-0 rounded-lg border px-2 py-1 text-center text-xs",
                d === day ? "border-accent-600 bg-accent-50 text-accent-700" : "border-slate-200 text-slate-700 hover:border-slate-300",
              )}
            >
              <div className="font-medium">{l.weekday}</div>
              <div>{l.day}</div>
            </button>
          );
        })}
      </div>
      {!serviceId ? (
        <p className="text-sm text-slate-500">Спершу оберіть послугу.</p>
      ) : isLoading ? (
        <p className="text-sm text-slate-500">Завантаження…</p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-slate-500">Вільних слотів немає.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {data.map((s) => {
            const sel = value?.start === s.start && value.staff_id === s.staff_id;
            return (
              <button
                key={s.start + s.staff_id}
                type="button"
                aria-pressed={sel}
                onClick={() => onChange(s)}
                className={cn(
                  "rounded-lg border px-2.5 py-1 text-sm",
                  sel ? "border-accent-600 bg-accent-50 text-accent-700" : "border-slate-200 text-slate-800 hover:border-slate-300",
                )}
              >
                {formatTime(s.start)}
                {!staffId && <span className="ml-1 text-xs text-slate-500">{s.staff_name}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
