"use client";

import { useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";
import type { Client, Priority, Ticket, TicketStatus } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/cn";

const PRIORITY: Record<Priority, { label: string; cls: string }> = {
  urgent: {label: "Терміново", cls: "bg-red-50 text-red-700 ring-red-200"},
  high: {label: "Високий", cls: "bg-orange-50 text-orange-700 ring-orange-200"},
  normal: {label: "Звичайний", cls: "bg-slate-100 text-slate-700 ring-slate-200"},
  low: {label: "Низький", cls: "bg-white text-slate-400 ring-slate-200"},
};

export function TicketList({ tenant }: { tenant: string }) {
  const [status, setStatus] = useState<TicketStatus>("open");
  const { data, mutate } = useApi<Ticket[]>(`/api/tenants/${tenant}/tickets?status=${status}`, { refreshMs: 3000 });
  const { data: clients } = useApi<Client[]>(`/api/tenants/${tenant}/clients`);
  const toast = useToast();
  const names = new Map((clients ?? []).map((c) => [c.id, c.name]));

  async function close(id: string) {
    try {
      await api.patch(`/api/tenants/${tenant}/tickets/${id}`, { status: "closed" });
      await mutate();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Не вдалося закрити");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {(["open", "closed"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              status === s ? "border-accent-600 bg-accent-50 text-accent-700" : "border-slate-200 text-slate-600",
            )}
          >
            {s === "open" ? "Відкриті" : "Закриті"}
          </button>
        ))}
      </div>
      {!data?.length ? (
        <p className="text-sm text-slate-500">Тікетів немає</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
          {data.map((t) => {
            const p = PRIORITY[t.priority];
            return (
              <li key={t.id} className="flex items-start justify-between gap-3 px-4 py-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", p.cls)}>
                      {p.label}
                    </span>
                    <span className="text-sm font-medium text-slate-900">{names.get(t.client_id) ?? t.client_id}</span>
                    <span className="text-xs text-slate-400">{formatDateTime(t.ts)}</span>
                  </div>
                  <p className="text-sm text-slate-700">{t.summary}</p>
                </div>
                {t.status === "open" && (
                  <Button variant="secondary" size="sm" onClick={() => void close(t.id)}>
                    Закрити
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
