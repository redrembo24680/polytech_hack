"use client";

import { useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";
import type { ScheduleRow, Service, Staff } from "@/lib/types";
import { WEEKDAYS } from "@/lib/schedule";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { StaffForm } from "./StaffForm";

function WeekSummary({ schedule }: { schedule: ScheduleRow[] }) {
  return (
    <div className="grid grid-cols-7 gap-1 text-center text-xs">
      {WEEKDAYS.map((d, i) => {
        const r = schedule.find((x) => x.weekday === i);
        return (
          <div key={d} className={r ? "rounded-md bg-accent-50 px-1 py-1 text-accent-700" : "rounded-md bg-slate-100 px-1 py-1 text-slate-400"}>
            <div className="font-medium">{d}</div>
            <div>{r ? `${r.start.slice(0, 5)}–${r.end.slice(0, 5)}` : "—"}</div>
          </div>
        );
      })}
    </div>
  );
}

export function StaffList({ tenant }: { tenant: string }) {
  const { data: staff, error, isLoading, mutate } = useApi<Staff[]>(`/api/tenants/${tenant}/staff`);
  const { data: services } = useApi<Service[]>(`/api/tenants/${tenant}/services`);
  const toast = useToast();
  const [form, setForm] = useState<{ staff?: Staff } | null>(null);
  const [del, setDel] = useState<Staff | null>(null);
  const [busy, setBusy] = useState(false);

  async function remove() {
    if (!del) return;
    setBusy(true);
    try {
      await api.del(`/api/tenants/${tenant}/staff/${del.id}`);
      toast.success("Майстра видалено");
      await mutate();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) toast.error("Є майбутні бронювання");
      else toast.error(e instanceof ApiError ? e.message : "Помилка");
    } finally {
      setBusy(false);
      setDel(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold text-slate-900">Майстри</h1>
        <Button onClick={() => setForm({})}>Новий майстер</Button>
      </div>
      {error && <p className="text-sm text-red-600">{error.message}</p>}
      {isLoading && <p className="text-slate-500">Завантаження…</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {(staff ?? []).map((s) => (
          <article key={s.id} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-lg font-semibold text-slate-900">{s.name}</h2>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => setForm({ staff: s })}>Редагувати</Button>
                <Button size="sm" variant="danger" onClick={() => setDel(s)}>Видалити</Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {s.service_ids.length === 0 && <span className="text-sm text-slate-400">Без послуг</span>}
              {s.service_ids.map((id) => (
                <Badge key={id} color="accent">{services?.find((x) => x.id === id)?.name ?? id}</Badge>
              ))}
            </div>
            <WeekSummary schedule={s.schedule} />
          </article>
        ))}
      </div>
      <StaffForm tenant={tenant} staff={form?.staff} services={services ?? []} open={form !== null} onClose={() => setForm(null)} onSaved={() => mutate()} />
      <Modal
        open={del !== null}
        onClose={() => setDel(null)}
        title="Видалити майстра?"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDel(null)}>Скасувати</Button>
            <Button variant="danger" loading={busy} onClick={remove}>Видалити</Button>
          </div>
        }
      >
        <p className="text-sm text-slate-700">Майстра «{del?.name}» буде видалено.</p>
      </Modal>
    </div>
  );
}
