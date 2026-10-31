"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import type { Booking, BookingStatus, Staff } from "@/lib/types";
import { cn } from "@/lib/cn";
import { dayBoundary, dayLabel, formatTime } from "@/lib/format";
import { addDays, todayKey, weekDays, weekStart } from "@/lib/week";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { BookingCard } from "./BookingCard";
import { BookingForm } from "./BookingForm";
import { STATUS_CHIP, STATUS_LABEL, lastByAgent } from "./status";

const STATUS_OPTIONS = (Object.keys(STATUS_LABEL) as BookingStatus[]).map((s) => ({ value: s, label: STATUS_LABEL[s] }));

export function BookingWeek({ tenant }: { tenant: string }) {
  const [monday, setMonday] = useState(() => weekStart(todayKey()));
  const [status, setStatus] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const days = weekDays(monday);
  const from = encodeURIComponent(dayBoundary(monday));
  const to = encodeURIComponent(dayBoundary(addDays(monday, 7)));
  const { data: bookings, error } = useApi<Booking[]>(
    `/api/tenants/${tenant}/bookings?from=${from}&to=${to}`,
    { refreshMs: 3000 },
  );
  const { data: staff } = useApi<Staff[]>(`/api/tenants/${tenant}/staff`);

  const visible = (bookings ?? []).filter((b) => !status || b.status === status);
  const today = todayKey();
  const first = dayLabel(days[0]);
  const last = dayLabel(days[6]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto text-2xl font-semibold text-slate-900">Бронювання</h1>
        <Select
          label="Статус"
          placeholder="Усі"
          options={STATUS_OPTIONS}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        />
        <Button onClick={() => setCreating(true)}>Нове бронювання</Button>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => setMonday(addDays(monday, -7))} aria-label="Попередній тиждень">←</Button>
        <Button variant="secondary" size="sm" onClick={() => setMonday(weekStart(todayKey()))}>Сьогодні</Button>
        <Button variant="secondary" size="sm" onClick={() => setMonday(addDays(monday, 7))} aria-label="Наступний тиждень">→</Button>
        <span className="text-sm font-medium text-slate-700">{first.day} — {last.day}</span>
      </div>

      {error && <p className="text-sm text-red-600">{error.message}</p>}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[56rem] table-fixed border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="w-24 p-2 text-left font-medium text-slate-500">Майстер</th>
              {days.map((d) => {
                const l = dayLabel(d);
                return (
                  <th key={d} className={cn("p-2 text-left font-medium", d === today ? "text-accent-700" : "text-slate-600")}>
                    {l.weekday}, {l.day}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {(staff ?? []).map((s) => (
              <tr key={s.id} className="border-b border-slate-100 last:border-0 align-top">
                <th scope="row" className="p-2 text-left font-medium text-slate-800">{s.name}</th>
                {days.map((d) => {
                  const cell = visible.filter((b) => b.staff_id === s.id && b.start.slice(0, 10) === d);
                  return (
                    <td key={d} className={cn("space-y-1 border-l border-slate-100 p-1.5", d === today && "bg-accent-50/40")}>
                      {cell.map((b) => (
                        <button
                          key={b.id}
                          type="button"
                          data-testid={`chip-${b.id}`}
                          onClick={() => setOpenId(b.id)}
                          className={cn(
                            "block w-full rounded-md border px-1.5 py-1 text-left text-xs leading-tight",
                            STATUS_CHIP[b.status],
                            lastByAgent(b) && "ring-2 ring-accent-500",
                          )}
                        >
                          <div className="flex items-center gap-1 font-semibold">
                            {formatTime(b.start)}
                            {lastByAgent(b) && <Badge color="accent" className="px-1 py-0 text-[10px]">AI</Badge>}
                          </div>
                          <div className="truncate">{b.client_name}</div>
                          <div className="truncate opacity-75">{b.service_name}</div>
                        </button>
                      ))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {bookings && visible.length === 0 && <p className="p-4 text-sm text-slate-500">На цьому тижні бронювань немає.</p>}
      </div>

      {openId && <BookingCard tenant={tenant} bookingId={openId} onClose={() => setOpenId(null)} />}
      {creating && (
        <BookingForm
          tenant={tenant}
          onClose={() => setCreating(false)}
          onCreated={(b) => {
            setCreating(false);
            setMonday(weekStart(b.start.slice(0, 10)));
            setOpenId(b.id);
          }}
        />
      )}
    </div>
  );
}
