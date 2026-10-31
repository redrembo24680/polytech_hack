"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Client } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

export function ClientForm({ tenant, client, open, onClose, onSaved }: {
  tenant: string; client?: Client; open: boolean; onClose: () => void; onSaved: (c: Client) => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title={client ? "Редагувати клієнта" : "Новий клієнт"} size="sm">
      {open && <Inner tenant={tenant} client={client} onClose={onClose} onSaved={onSaved} />}
    </Modal>
  );
}

function Inner({ tenant, client, onClose, onSaved }: { tenant: string; client?: Client; onClose: () => void; onSaved: (c: Client) => void }) {
  const toast = useToast();
  const [name, setName] = useState(client?.name ?? "");
  const [phone, setPhone] = useState(client?.phone ? `+${client.phone}` : "");
  const [notes, setNotes] = useState(client?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setErr("Вкажіть ім'я");
    if (!phone.replace(/\D/g, "")) return setErr("Вкажіть телефон");
    setBusy(true);
    setErr(null);
    try {
      const saved = client
        ? await api.patch<Client>(`/api/tenants/${tenant}/clients/${client.id}`, {
            ...(name.trim() !== client.name && { name: name.trim() }),
            ...(phone.replace(/\D/g, "") !== client.phone && { phone }),
            ...(notes !== client.notes && { notes }),
          })
        : await api.post<Client>(`/api/tenants/${tenant}/clients`, { name: name.trim(), phone, notes });
      toast.success(client ? "Клієнта оновлено" : "Клієнта створено");
      onSaved(saved);
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
      <Input label="Ім'я" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      <Input label="Телефон" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+380 67 123 45 67" inputMode="tel" />
      <Textarea label="Нотатки" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {err && <p className="text-sm text-red-600">{err}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Скасувати</Button>
        <Button type="submit" loading={busy}>Зберегти</Button>
      </div>
    </form>
  );
}
