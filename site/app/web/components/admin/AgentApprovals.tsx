"use client";

// Agent approvals panel. Agent API base URL: NEXT_PUBLIC_AGENT_URL (default http://localhost:8000).
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

const TOOL_LABELS: Record<string, string> = {
  apply_goodwill_exception: "Виняток: зберегти передоплату",
  refund_prepayment: "Повернення передоплати",
  cancel_booking: "Скасування запису",
  reschedule_booking: "Перенесення запису",
  waive_no_show_fee: "Зняти штраф за неявку",
};

interface Approval {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  reason: string | null;
}

function argsLine(args: Record<string, unknown>): string {
  return (["booking_id", "amount", "start"] as const)
    .filter((k) => args?.[k] != null)
    .map((k) => `${k}: ${String(args[k])}`)
    .join(" · ");
}

export function AgentApprovals({ tenant }: { tenant: string }) {
  const [items, setItems] = useState<Approval[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${AGENT_URL}/tenants/${tenant}/approvals?status=pending`);
      if (r.ok) setItems(((await r.json()) as { approvals: Approval[] }).approvals);
    } catch {
      /* agent offline: keep last state */
    }
  }, [tenant]);

  useEffect(() => {
    const first = setTimeout(() => void load(), 0);
    const t = setInterval(() => void load(), 2000);
    return () => {
      clearTimeout(first);
      clearInterval(t);
    };
  }, [load]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 5000);
    return () => clearTimeout(t);
  }, [flash]);

  async function decide(a: Approval, approve: boolean) {
    setBusy(a.id);
    try {
      const r = await fetch(`${AGENT_URL}/approvals/${a.id}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approve, note: notes[a.id]?.trim() || null, by: "Адміністратор" }),
      });
      const data = (await r.json().catch(() => ({}))) as {
        result?: { status?: string };
        error?: string | { message?: string };
      };
      if (r.ok || r.status === 409) {
        setItems((xs) => xs.filter((x) => x.id !== a.id));
        const err = typeof data.error === "string" ? data.error : data.error?.message;
        setFlash(`Виконано: ${err ?? data.result?.status ?? (approve ? "схвалено" : "відхилено")}`);
      } else {
        const err = typeof data.error === "string" ? data.error : data.error?.message;
        setFlash(`Помилка: ${err ?? r.status}`);
      }
    } catch {
      setFlash("Помилка: агент недоступний");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-base font-semibold text-slate-900">Погодження дій агента</h2>
        <span className="grid h-6 min-w-6 place-items-center rounded-full bg-accent-600 px-1.5 text-xs text-white">
          {items.length}
        </span>
      </div>
      {flash && <p className="mb-3 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">{flash}</p>}
      {items.length === 0 ? (
        <p className="text-sm text-slate-400">Немає запитів від агента</p>
      ) : (
        <ul className="space-y-3">
          {items.map((a) => (
            <li key={a.id} className="rounded-xl border border-slate-200 p-4">
              <div className="font-medium text-slate-900">{TOOL_LABELS[a.tool] ?? a.tool}</div>
              <div className="mt-0.5 text-xs text-slate-500">{argsLine(a.args)}</div>
              {a.reason && <p className="mt-2 text-sm text-slate-700">{a.reason}</p>}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  value={notes[a.id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [a.id]: e.target.value }))}
                  placeholder="Примітка (необов'язково)"
                  className="h-8 min-w-48 flex-1 rounded-lg border border-slate-300 px-3 text-sm"
                />
                <Button size="sm" disabled={busy === a.id} onClick={() => void decide(a, true)}>
                  Схвалити
                </Button>
                <Button size="sm" variant="secondary" disabled={busy === a.id} onClick={() => void decide(a, false)}>
                  Відхилити
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
