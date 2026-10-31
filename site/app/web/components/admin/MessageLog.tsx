"use client";

import { useApi } from "@/lib/api";
import type { Client, OutgoingMessage } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/format";

export function MessageLog({ tenant }: { tenant: string }) {
  const { data } = useApi<OutgoingMessage[]>(`/api/tenants/${tenant}/messages`, { refreshMs: 3000 });
  const { data: clients } = useApi<Client[]>(`/api/tenants/${tenant}/clients`);
  const names = new Map((clients ?? []).map((c) => [c.id, c.name]));
  if (!data?.length) return <p className="text-sm text-slate-500">Вихідних повідомлень ще немає</p>;
  return (
    <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
      {data.map((m) => (
        <li key={m.id} className="space-y-1 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-slate-900">{names.get(m.client_id) ?? m.client_id}</span>
            <Badge color={m.channel === "sms" ? "amber" : "blue"}>{m.channel === "sms" ? "SMS" : "Чат"}</Badge>
            <span className="text-xs text-slate-400">{formatDateTime(m.ts)}</span>
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-700">{m.text}</p>
        </li>
      ))}
    </ul>
  );
}
