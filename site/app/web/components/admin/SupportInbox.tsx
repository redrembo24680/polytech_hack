"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { ConversationList } from "./ConversationList";
import { ConversationView } from "./ConversationView";
import { TicketList } from "./TicketList";
import { MessageLog } from "./MessageLog";

const TABS = [
  { id: "conv", label: "Розмови" },
  { id: "tickets", label: "Тікети" },
  { id: "messages", label: "Повідомлення" },
] as const;

export function SupportInbox({ tenant }: { tenant: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("conv");
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Підтримка</h1>
      <div role="tablist" className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium",
              tab === t.id
                ? "border-accent-600 text-accent-700"
                : "border-transparent text-slate-500 hover:text-slate-800",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "conv" && (
        <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
          <ConversationList tenant={tenant} selectedId={selected} onSelect={setSelected} />
          {selected ? (
            <ConversationView key={selected} tenant={tenant} conversationId={selected} />
          ) : (
            <div className="flex min-h-64 items-center justify-center rounded-2xl border border-dashed border-slate-300 text-sm text-slate-400">
              Оберіть розмову
            </div>
          )}
        </div>
      )}
      {tab === "tickets" && <TicketList tenant={tenant} />}
      {tab === "messages" && <MessageLog tenant={tenant} />}
    </div>
  );
}
