"use client";

import { useApi } from "@/lib/api";
import type { Conversation } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/cn";

export function convName(c: Conversation): string {
  return c.client_name || c.visitor_name || "Відвідувач";
}

export function ConversationList({
  tenant,
  selectedId,
  onSelect,
}: {
  tenant: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { data, isLoading } = useApi<Conversation[]>(`/api/tenants/${tenant}/support/conversations`, {
    refreshMs: 3000,
  });
  if (isLoading && !data) return <p className="text-sm text-slate-500">Завантаження…</p>;
  if (!data?.length) return <p className="text-sm text-slate-500">Розмов ще немає</p>;
  return (
    <ul className="max-h-[70vh] divide-y divide-slate-100 overflow-y-auto rounded-2xl border border-slate-200 bg-white">
      {data.map((c) => (
        <li key={c.id}>
          <button
            onClick={() => onSelect(c.id)}
            className={cn(
              "flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-slate-50",
              selectedId === c.id && "bg-accent-50",
            )}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium text-slate-900">{convName(c)}</span>
              <Badge color={c.status === "open" ? "green" : "gray"}>
                {c.status === "open" ? "Відкрита" : "Закрита"}
              </Badge>
            </span>
            <span className="truncate text-sm text-slate-600">{c.last_message?.text ?? "Без повідомлень"}</span>
            <span className="text-xs text-slate-400">{formatDateTime(c.last_message?.ts ?? c.created_at)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
