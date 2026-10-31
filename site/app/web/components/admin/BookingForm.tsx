"use client";

import { useState } from "react";
import { mutate as globalMutate } from "swr";
import { api, ApiError, useApi } from "@/lib/api";
import type { Booking, Client, Service, Slot, Staff } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/Toast";
import { SlotPicker } from "./SlotPicker";

export interface BookingFormProps {
  tenant: string;
  onClose: () => void;
  onCreated: (b: Booking) => void;
}

export function BookingForm({ tenant, onClose, onCreated }: BookingFormProps) {
  const toast = useToast();
  const [isNew, setIsNew] = useState(false);
  const [q, setQ] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [staffId, setStaffId] = useState("");
  const [slot, setSlot] = useState<Slot | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: services } = useApi<Service[]>(`/api/tenants/${tenant}/services`);
  const { data: staff } = useApi<Staff[]>(`/api/tenants/${tenant}/staff`);
  const { data: found } = useApi<Client[]>(!isNew && q.trim().length >= 2 ? `/api/tenants/${tenant}/clients?q=${encodeURIComponent(q.trim())}` : null);

  const staffOptions = (staff ?? [])
    .filter((s) => !serviceId || s.service_ids.includes(serviceId))
    .map((s) => ({ value: s.id, label: s.name }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!isNew && !client) return toast.error("Оберіть клієнта");
    if (isNew && (!name.trim() || !phone.trim())) return toast.error("Вкажіть ім'я та телефон");
    if (!serviceId || !slot) return toast.error("Оберіть послугу та слот");
    setBusy(true);
    try {
      const b = await api.post<Booking>(`/api/tenants/${tenant}/bookings`, {
        ...(isNew ? { client: { name: name.trim(), phone: phone.trim() } } : { client_id: client!.id }),
        service_id: serviceId,
        staff_id: slot.staff_id,
        start: slot.start,
        by: "human:admin",
      });
      await globalMutate((k) => typeof k === "string" && k.includes(`/tenants/${tenant}/bookings?`));
      toast.success("Бронювання створено");
      onCreated(b);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Не вдалося створити бронювання");
      setSlot(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open onClose={onClose} title="Нове бронювання" size="lg">
      <form onSubmit={submit} className="space-y-4">
        <div className="flex gap-2">
          <Button size="sm" variant={isNew ? "secondary" : "primary"} onClick={() => setIsNew(false)}>Існуючий клієнт</Button>
          <Button size="sm" variant={isNew ? "primary" : "secondary"} onClick={() => setIsNew(true)}>Новий клієнт</Button>
        </div>

        {isNew ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Ім'я" value={name} onChange={(e) => setName(e.target.value)} />
            <Input label="Телефон" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+380 67 123 45 67" />
          </div>
        ) : client ? (
          <div className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <span>{client.name} · {client.phone}</span>
            <Button size="sm" variant="ghost" onClick={() => setClient(null)}>Змінити</Button>
          </div>
        ) : (
          <div className="space-y-2">
            <Input label="Пошук клієнта (ім'я або телефон)" value={q} onChange={(e) => setQ(e.target.value)} />
            {found && found.length === 0 && <p className="text-sm text-slate-500">Нікого не знайдено.</p>}
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 empty:hidden">
              {(found ?? []).slice(0, 6).map((c) => (
                <li key={c.id}>
                  <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => setClient(c)}>
                    {c.name} · {c.phone}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="Послуга"
            placeholder="Оберіть"
            options={(services ?? []).map((s) => ({ value: s.id, label: s.name }))}
            value={serviceId}
            onChange={(e) => { setServiceId(e.target.value); setStaffId(""); setSlot(null); }}
          />
          <Select
            label="Майстер"
            placeholder="Будь-хто"
            options={staffOptions}
            value={staffId}
            onChange={(e) => { setStaffId(e.target.value); setSlot(null); }}
          />
        </div>

        <SlotPicker tenant={tenant} serviceId={serviceId || null} staffId={staffId || undefined} value={slot} onChange={setSlot} />

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Скасувати</Button>
          <Button type="submit" loading={busy}>Створити</Button>
        </div>
      </form>
    </Modal>
  );
}
