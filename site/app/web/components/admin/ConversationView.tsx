"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";
import type { ChatMessage, Conversation } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { convName } from "./ConversationList";

const POLL_MS = 3000;

function merge(prev: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const ids = new Set(prev.map((m) => m.id));
  const fresh = incoming.filter((m) => !ids.has(m.id));
  if (!fresh.length) return prev;
  return [...prev, ...fresh].sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
}

export function ConversationView({ tenant, conversationId }: { tenant: string; conversationId: string }) {
  const base = `/api/tenants/${tenant}/support/conversations`;
  const { data: list, mutate: mutateList } = useApi<Conversation[]>(base, { refreshMs: 3000 });
  const conv = list?.find((c) => c.id === conversationId);
  const toast = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const lastTs = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    lastTs.current = messages.length ? messages[messages.length - 1].ts : null;
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const q = lastTs.current ? `?after=${encodeURIComponent(lastTs.current)}` : "";
        const fresh = await api.get<ChatMessage[]>(`${base}/${conversationId}/messages${q}`);
        if (!stopped && fresh.length) setMessages((p) => merge(p, fresh));
      } catch {
        /* retry on next tick */
      }
    };
    void tick();
    const t = setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, [base, conversationId]);

  async function send() {
    const value = text.trim();
    if (!value || sending) return;
    setSending(true);
    try {
      const created = await api.post<ChatMessage | ChatMessage[]>(`${base}/${conversationId}/reply`, {
        text: value,
        role: "human",
      });
      setMessages((p) => merge(p, Array.isArray(created) ? created : [created]));
      setText("");
      void mutateList();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Не вдалося надіслати");
    } finally {
      setSending(false);
    }
  }

  async function toggle() {
    if (!conv) return;
    try {
      await api.patch(`${base}/${conversationId}`, { status: conv.status === "open" ? "closed" : "open" });
      await mutateList();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Не вдалося змінити статус");
    }
  }

  return (
    <div className="flex h-[70vh] min-h-96 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2.5">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">{conv ? convName(conv) : "…"}</div>
          {conv?.visitor_phone && <div className="text-xs text-slate-500">{conv.visitor_phone}</div>}
        </div>
        {conv && (
          <Button variant="secondary" size="sm" onClick={() => void toggle()}>
            {conv.status === "open" ? "Закрити" : "Відкрити знову"}
          </Button>
        )}
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && <p className="py-8 text-center text-sm text-slate-400">Повідомлень ще немає</p>}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
        <textarea
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Відповідь клієнту…"
          aria-label="Відповідь"
          className="max-h-32 min-h-10 flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-200"
        />
        <Button onClick={() => void send()} loading={sending} disabled={!text.trim()}>
          Надіслати
        </Button>
      </div>
    </div>
  );
}
