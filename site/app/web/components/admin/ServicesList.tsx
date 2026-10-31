"use client";

import { useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";
import type { Service } from "@/lib/types";
import { formatDuration, formatPrice } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Table } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import { ServiceForm } from "./ServiceForm";

export function ServicesList({ tenant }: { tenant: string }) {
  const { data, error, isLoading, mutate } = useApi<Service[]>(`/api/tenants/${tenant}/services`);
  const toast = useToast();
  const [form, setForm] = useState<{ service?: Service } | null>(null);
  const [del, setDel] = useState<Service | null>(null);
  const [busy, setBusy] = useState(false);

  async function remove() {
    if (!del) return;
    setBusy(true);
    try {
      await api.del(`/api/tenants/${tenant}/services/${del.id}`);
      toast.success("Послугу видалено");
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
        <h1 className="text-2xl font-semibold text-slate-900">Послуги</h1>
        <Button onClick={() => setForm({})}>Нова послуга</Button>
      </div>
      {error && <p className="text-sm text-red-600">{error.message}</p>}
      <Table
        columns={[
          { key: "name", header: "Назва", render: (s) => <span className="font-medium text-slate-900">{s.name}</span> },
          { key: "d", header: "Тривалість", render: (s) => formatDuration(s.duration_min) },
          { key: "p", header: "Ціна", render: (s) => formatPrice(s.price) },
          {
            key: "a",
            header: "",
            render: (s) => (
              <span className="flex justify-end gap-2">
                <Button size="sm" variant="secondary" onClick={() => setForm({ service: s })}>Редагувати</Button>
                <Button size="sm" variant="danger" onClick={() => setDel(s)}>Видалити</Button>
              </span>
            ),
          },
        ]}
        rows={data ?? []}
        rowKey={(s) => s.id}
        empty={isLoading ? "Завантаження…" : "Послуг ще немає"}
      />
      <ServiceForm tenant={tenant} service={form?.service} open={form !== null} onClose={() => setForm(null)} onSaved={() => mutate()} />
      <Modal
        open={del !== null}
        onClose={() => setDel(null)}
        title="Видалити послугу?"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDel(null)}>Скасувати</Button>
            <Button variant="danger" loading={busy} onClick={remove}>Видалити</Button>
          </div>
        }
      >
        <p className="text-sm text-slate-700">Послугу «{del?.name}» буде видалено.</p>
      </Modal>
    </div>
  );
}
