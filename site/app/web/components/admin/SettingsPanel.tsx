"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, useApi } from "@/lib/api";
import type { Tenant } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { PolicyForm } from "./PolicyForm";

export function SettingsPanel({ tenant }: { tenant: string }) {
  const { data, mutate } = useApi<Tenant>(`/api/tenants/${tenant}`);
  if (!data) return <p className="text-sm text-slate-500">Завантаження…</p>;
  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-slate-900">Налаштування</h1>
      <BusinessForm tenant={tenant} data={data} onSaved={() => mutate()} />
      <PolicyForm
        tenant={tenant}
        key={JSON.stringify(data.policy)}
        policy={data.policy}
        onSaved={() => void mutate()}
      />
    </div>
  );
}

function BusinessForm({
  tenant,
  data,
  onSaved,
}: {
  tenant: string;
  data: Tenant;
  onSaved: () => Promise<unknown>;
}) {
  const path = `/api/tenants/${tenant}`;
  const router = useRouter();
  const toast = useToast();
  const [form, setForm] = useState({
    name: data.name,
    description: data.description,
    address: data.address,
    phone: data.phone,
    instagram: data.instagram ?? "",
  });
  const [saving, setSaving] = useState(false);
  const set =
    (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error("Вкажіть назву");
      return;
    }
    setSaving(true);
    try {
      await api.patch<Tenant>(path, { ...form, name: form.name.trim() });
      await onSaved();
      router.refresh();
      toast.success("Дані збережено");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Не вдалося зберегти",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={save}
      className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5"
    >
      <h2 className="text-base font-semibold text-slate-900">Дані бізнесу</h2>
      <Input label="Назва" value={form.name} onChange={set("name")} required />
      <Textarea
        label="Опис"
        value={form.description}
        onChange={set("description")}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Адреса" value={form.address} onChange={set("address")} />
        <Input label="Телефон" value={form.phone} onChange={set("phone")} />
      </div>
      <Input
        label="Instagram"
        value={form.instagram}
        onChange={set("instagram")}
      />
      <Button type="submit" loading={saving}>
        Зберегти
      </Button>
    </form>
  );
}
