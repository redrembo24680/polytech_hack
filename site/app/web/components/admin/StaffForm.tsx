"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Service, Staff } from "@/lib/types";
import { daysToRows, rowsToDays, validateDays, type DayState } from "@/lib/schedule";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ScheduleEditor } from "./ScheduleEditor";

export function StaffForm({ tenant, staff, services, open, onClose, onSaved }: {
  tenant: string; staff?: Staff; services: Service[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title={staff ? "Редагувати майстра" : "Новий майстер"} size="lg">
      {open && <Inner tenant={tenant} staff={staff} services={services} onClose={onClose} onSaved={onSaved} />}
    </Modal>
  );
}

function Inner({ tenant, staff, services, onClose, onSaved }: {
  tenant: string; staff?: Staff; services: Service[]; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(staff?.name ?? "");
  const [ids, setIds] = useState<string[]>(staff?.service_ids ?? []);
  const [days, setDays] = useState<DayState[]>(() => rowsToDays(staff?.schedule ?? []));
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const toggle = (id: string) => setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setErr("Вкажіть ім'я");
    if (validateDays(days).some(Boolean)) return setErr("Виправте помилки в графіку");
    setBusy(true);
    setErr(null);
    try {
      const base = `/api/tenants/${tenant}/staff`;
      const body = { name: name.trim(), service_ids: ids };
      const existingId = staff?.id ?? createdId;
      let id: string;
      if (existingId) {
        await api.patch<Staff>(`${base}/${existingId}`, body);
        id = existingId;
      } else {
        const created = await api.post<Staff>(base, body);
        id = created.id;
        setCreatedId(id);
        onSaved();
      }
      await api.put(`${base}/${id}/schedule`, daysToRows(days));
      toast.success(staff ? "Майстра оновлено" : "Майстра створено");
      onSaved();
      onClose();
    } catch (e) {
      const m = e instanceof ApiError ? e.message : "Помилка";
      setErr(m);
      toast.error(m);
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Input label="Ім'я" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">Послуги</legend>
        <div className="grid gap-1 sm:grid-cols-2">
          {services.map((s) => (
            <label key={s.id} className="flex items-center gap-2 text-sm text-slate-800">
              <input type="checkbox" checked={ids.includes(s.id)} onChange={() => toggle(s.id)} />
              {s.name}
            </label>
          ))}
          {services.length === 0 && <span className="text-sm text-slate-400">Послуг ще немає</span>}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">Графік роботи</legend>
        <ScheduleEditor value={days} onChange={setDays} />
      </fieldset>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Скасувати</Button>
        <Button type="submit" loading={busy}>Зберегти</Button>
      </div>
    </form>
  );
}
