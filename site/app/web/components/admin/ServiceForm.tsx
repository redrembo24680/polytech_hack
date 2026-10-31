"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Service } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

export function ServiceForm({ tenant, service, open, onClose, onSaved }: {
  tenant: string; service?: Service; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title={service ? "Редагувати послугу" : "Нова послуга"} size="sm">
      {open && <Inner tenant={tenant} service={service} onClose={onClose} onSaved={onSaved} />}
    </Modal>
  );
}

function Inner({ tenant, service, onClose, onSaved }: { tenant: string; service?: Service; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(service?.name ?? "");
  const [duration, setDuration] = useState(String(service?.duration_min ?? 60));
  const [price, setPrice] = useState(String(service?.price ?? 0));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const d = Number(duration);
    const p = Number(price);
    if (!name.trim()) return setErr("Вкажіть назву");
    if (!Number.isInteger(d) || d <= 0) return setErr("Тривалість має бути більшою за 0");
    if (!Number.isInteger(p) || p < 0) return setErr("Ціна не може бути від'ємною");
    setBusy(true);
    setErr(null);
    try {
      const body = { name: name.trim(), duration_min: d, price: p };
      if (service) await api.patch(`/api/tenants/${tenant}/services/${service.id}`, body);
      else await api.post(`/api/tenants/${tenant}/services`, body);
      toast.success(service ? "Послугу оновлено" : "Послугу створено");
      onSaved();
      onClose();
    } catch (e) {
      const m = e instanceof ApiError ? e.message : "Помилка";
      setErr(m);
      toast.error(m);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <Input label="Назва" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      <Input label="Тривалість, хв" type="number" min={1} value={duration} onChange={(e) => setDuration(e.target.value)} />
      <Input label="Ціна, грн" type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} />
      {err && <p className="text-sm text-red-600">{err}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Скасувати</Button>
        <Button type="submit" loading={busy}>Зберегти</Button>
      </div>
    </form>
  );
}
