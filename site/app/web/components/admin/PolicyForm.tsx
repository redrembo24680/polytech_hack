"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AgentPermissions, Policy } from "@/lib/types";
import { policyToText } from "@/lib/policy-text";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/Toast";

const AUTO = [
  { value: "auto", label: "Сам" },
  { value: "approval", label: "З погодженням" },
];
const GATE = [...AUTO, { value: "forbidden", label: "Заборонено" }];
const REFUND = [
  { value: "auto_under_limit", label: "Сам до ліміту" },
  { value: "approval", label: "З погодженням" },
  { value: "forbidden", label: "Заборонено" },
];

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-slate-300 accent-accent-600"
      />
      {label}
    </label>
  );
}

const num = (v: string) => (v === "" ? 0 : Math.max(0, Math.floor(Number(v)) || 0));

export function PolicyForm({
  tenant,
  policy,
  onSaved,
}: {
  tenant: string;
  policy: Policy;
  onSaved?: (p: Policy) => void;
}) {
  const [p, setP] = useState<Policy>(policy);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const perm = p.agent_permissions;
  const setPerm = <K extends keyof AgentPermissions>(k: K, v: AgentPermissions[K]) =>
    setP((x) => ({ ...x, agent_permissions: { ...x.agent_permissions, [k]: v } }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const saved = await api.put<Policy>(`/api/tenants/${tenant}/policy`, p);
      setP(saved);
      onSaved?.(saved);
      toast.success("Політику збережено");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Не вдалося зберегти");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">Політика</h2>

      <fieldset className="space-y-4">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Правила для клієнтів</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Вікно скасування (год)"
            type="number"
            min={0}
            value={p.cancellation_window_hours}
            onChange={(e) => setP({ ...p, cancellation_window_hours: num(e.target.value) })}
          />
          <Input
            label="Штраф за неявку (грн)"
            type="number"
            min={0}
            value={p.no_show_fee}
            onChange={(e) => setP({ ...p, no_show_fee: num(e.target.value) })}
          />
        </div>
        <Toggle
          label="Пізня зміна втрачає передоплату"
          checked={p.late_change_forfeits_prepayment}
          onChange={(v) => setP({ ...p, late_change_forfeits_prepayment: v })}
        />
        <Toggle
          label="Потрібна передоплата"
          checked={p.prepayment_required}
          onChange={(v) => setP({ ...p, prepayment_required: v })}
        />
        <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Так бачить клієнт</div>
          <ul className="list-disc space-y-0.5 pl-5">
            {policyToText(p).map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Що AI-агент може робити сам</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Перенесення"
            options={AUTO}
            value={perm.reschedule}
            onChange={(e) => setPerm("reschedule", e.target.value as AgentPermissions["reschedule"])}
          />
          <Select
            label="Скасування"
            options={AUTO}
            value={perm.cancel}
            onChange={(e) => setPerm("cancel", e.target.value as AgentPermissions["cancel"])}
          />
          <Select
            label="Повернення передоплати"
            options={REFUND}
            value={perm.refund}
            onChange={(e) => setPerm("refund", e.target.value as AgentPermissions["refund"])}
          />
          <Input
            label="Ліміт авто-повернення (грн)"
            type="number"
            min={0}
            disabled={perm.refund !== "auto_under_limit"}
            value={perm.refund_auto_limit}
            onChange={(e) => setPerm("refund_auto_limit", num(e.target.value))}
          />
          <Select
            label="Виняток з доброї волі"
            options={GATE}
            value={perm.goodwill_exception}
            onChange={(e) => setPerm("goodwill_exception", e.target.value as AgentPermissions["goodwill_exception"])}
          />
          <Input
            label="Винятків на клієнта за 180 днів"
            type="number"
            min={0}
            value={perm.goodwill_per_client_per_180d}
            onChange={(e) => setPerm("goodwill_per_client_per_180d", num(e.target.value))}
          />
          <Select
            label="Зняття штрафу за неявку"
            options={GATE}
            value={perm.waive_no_show_fee}
            onChange={(e) => setPerm("waive_no_show_fee", e.target.value as AgentPermissions["waive_no_show_fee"])}
          />
        </div>
        <Toggle
          label="Виняток лише клієнтам без неявок"
          checked={perm.goodwill_requires_zero_no_shows}
          onChange={(v) => setPerm("goodwill_requires_zero_no_shows", v)}
        />
      </fieldset>

      <Button type="submit" loading={saving}>
        Зберегти політику
      </Button>
    </form>
  );
}
