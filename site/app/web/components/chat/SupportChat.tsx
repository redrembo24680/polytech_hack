"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ChatMessage, Conversation } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { MessageBubble, TypingIndicator } from "./MessageBubble";
import { StartForm } from "./StartForm";
import { OtpStep } from "./OtpStep";

const POLL_MS = 2000;
// Demo-only: the code is a client-side constant. A real deployment would use an SMS gateway
// and verify the code server-side.
const SMS_DEMO_CODE = process.env.NEXT_PUBLIC_SMS_DEMO_CODE ?? "1234";
const storageKey = (tenant: string) => `support:${tenant}`;

function readStored(tenant: string): { conversationId: string; verified: boolean } | null {
  try {
    const raw = localStorage.getItem(storageKey(tenant));
    if (!raw) return null;
    const j = JSON.parse(raw);
    if (!j.conversationId) return null;
    return { conversationId: j.conversationId, verified: j.verified === 1 };
  } catch {
    return null;
  }
}
function writeStored(tenant: string, conversationId: string | null, verified = false) {
  try {
    if (conversationId)
      localStorage.setItem(
        storageKey(tenant),
        JSON.stringify(verified ? { conversationId, verified: 1 } : { conversationId }),
      );
    else localStorage.removeItem(storageKey(tenant));
  } catch {
    /* storage unavailable */
  }
}

// Merge by id, keep chronological order.
function merge(prev: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const ids = new Set(prev.map((m) => m.id));
  const fresh = incoming.filter((m) => !ids.has(m.id));
  if (!fresh.length) return prev;
  return [...prev, ...fresh].sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
}

export function SupportChat({ tenant, embed }: { tenant: string; embed: boolean }) {
  const base = `/api/tenants/${tenant}/support/conversations`;

  const [phase, setPhase] = useState<"loading" | "form" | "otp" | "chat" | "retry">("loading");
  const [attempt, setAttempt] = useState(0);
  const [convId, setConvId] = useState<string | null>(null);
  const [otpTarget, setOtpTarget] = useState<{ clientId: string; phone: string } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  // Optimistic client messages awaiting the POST response; rendered after server messages.
  const [pending, setPending] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const lastTs = useRef<string | null>(null);

  const reset = useCallback(() => {
    writeStored(tenant, null);
    setConvId(null);
    setMessages([]);
    setPending([]);
    lastTs.current = null;
    setError(null);
    setPhase("form");
  }, [tenant]);

  // Resume stored conversation.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setPhase("loading");
      const stored = readStored(tenant);
      const id = stored?.conversationId;
      if (!id) {
        setPhase("form");
        return;
      }
      try {
        const conv = await api.get<Conversation>(`${base}/${id}`);
        if (conv.status === "closed") throw new ApiError("closed", "closed", 409);
        const msgs = await api.get<ChatMessage[]>(`${base}/${id}/messages`);
        if (cancelled) return;
        setConvId(id);
        setMessages(msgs);
        if (!stored.verified && conv.client_id && msgs.length === 0) {
          // Started but never confirmed the code: back to the code step.
          const phone = conv.visitor_phone ?? "";
          setOtpTarget({ clientId: conv.client_id, phone });
          await api
            .post(`/api/tenants/${tenant}/messages`, {
              client_id: conv.client_id,
              channel: "sms",
              text: `Код підтвердження для чату підтримки: ${SMS_DEMO_CODE}`,
            })
            .catch(() => undefined);
          if (cancelled) return;
          setPhase("otp");
        } else {
          setPhase("chat");
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && (e.status === 404 || e.status === 405 || e.code === "closed")) reset();
        else setPhase("retry");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant, base, reset, attempt]);

  useEffect(() => {
    lastTs.current = messages.length ? messages[messages.length - 1].ts : null;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending, sending]);

  // Poll for asynchronously posted agent/human messages.
  useEffect(() => {
    if (phase !== "chat" || !convId) return;
    let stopped = false;
    const tick = async () => {
      try {
        const q = lastTs.current ? `?after=${encodeURIComponent(lastTs.current)}` : "";
        const fresh = await api.get<ChatMessage[]>(`${base}/${convId}/messages${q}`);
        if (stopped || !fresh.length) return;
        setMessages((p) => merge(p, fresh));
        // Server copy of an in-flight client message arrived: drop the temp one.
        const texts = fresh.filter((m) => m.role === "client").map((m) => m.text);
        if (texts.length) {
          setPending((p) => {
            const rest = [...texts];
            return p.filter((m) => {
              const i = rest.indexOf(m.text);
              if (i < 0) return true;
              rest.splice(i, 1);
              return false;
            });
          });
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404 && !stopped) reset();
      }
    };
    const t = setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, [phase, convId, base, reset]);

  async function sendCode(clientId: string) {
    await api.post(`/api/tenants/${tenant}/messages`, {
      client_id: clientId,
      channel: "sms",
      text: `Код підтвердження для чату підтримки: ${SMS_DEMO_CODE}`,
    });
  }

  async function start(name: string, phone: string) {
    setStarting(true);
    setError(null);
    try {
      const conv = await api.post<Conversation>(base, { client_name: name, client_phone: phone });
      setConvId(conv.id);
      setMessages([]);
      if (conv.client_id) {
        // Known client: SMS a code first. Unknown phone: nobody to SMS, open the chat
        // (the agent will ask for the phone).
        await sendCode(conv.client_id);
        writeStored(tenant, conv.id, false);
        setOtpTarget({ clientId: conv.client_id, phone });
        setPhase("otp");
      } else {
        writeStored(tenant, conv.id, true);
        setPhase("chat");
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не вдалося почати чат");
    } finally {
      setStarting(false);
    }
  }

  function verified() {
    if (convId) writeStored(tenant, convId, true);
    setPhase("chat");
  }

  async function send() {
    const value = text.trim();
    if (!value || sending || !convId) return;
    const tempId = `tmp-${Date.now()}`;
    const optimistic: ChatMessage = {
      id: tempId,
      conversation_id: convId,
      role: "client",
      text: value,
      ts: new Date().toISOString(),
    };
    setText("");
    setError(null);
    setSending(true);
    setPending((p) => [...p, optimistic]);
    try {
      const created = await api.post<ChatMessage[]>(`${base}/${convId}/messages`, { text: value });
      setMessages((p) => merge(p, created));
      setPending((p) => p.filter((m) => m.id !== tempId));
    } catch (e) {
      setPending((p) => p.filter((m) => m.id !== tempId));
      setText(value);
      if (e instanceof ApiError && (e.status === 404 || e.status === 409)) reset();
      else setError("Не вдалося надіслати повідомлення. Спробуйте ще раз.");
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <div
      className={cn(
        "flex min-h-0 flex-col overflow-hidden bg-slate-50",
        embed
          ? "h-dvh flex-1"
          : "mx-auto h-[calc(100dvh-9rem)] min-h-[28rem] w-full max-w-2xl rounded-2xl border border-slate-200 shadow-sm",
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          <span className="text-sm font-semibold text-slate-900">Підтримка</span>
        </div>
        {phase === "chat" && (
          <Button variant="ghost" size="sm" onClick={reset}>
            Нова розмова
          </Button>
        )}
      </div>

      {phase === "loading" && <div className="flex-1" />}
      {phase === "retry" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center">
          <p className="text-sm text-red-600">Не вдалося завантажити розмову</p>
          <Button size="sm" onClick={() => setAttempt((n) => n + 1)}>
            Спробувати ще
          </Button>
        </div>
      )}
      {phase === "form" && <StartForm onStart={start} busy={starting} error={error} />}
      {phase === "otp" && otpTarget && (
        <OtpStep
          phone={otpTarget.phone}
          expected={SMS_DEMO_CODE}
          onVerified={verified}
          onResend={() => sendCode(otpTarget.clientId).catch(() => undefined)}
          onCancel={reset}
        />
      )}
      {phase === "chat" && (
        <>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
            {messages.length === 0 && pending.length === 0 && !sending && (
              <p className="py-8 text-center text-sm text-slate-400">
                Напишіть, чим можемо допомогти
              </p>
            )}
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {pending.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {sending && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
          {error && <p className="px-4 pb-1 text-sm text-red-600">{error}</p>}
          <div className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
            <textarea
              ref={inputRef}
              rows={1}
              value={text}
              disabled={sending}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ваше повідомлення…"
              aria-label="Повідомлення"
              className="max-h-32 min-h-10 flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-200 disabled:bg-slate-50 disabled:text-slate-400"
            />
            <Button onClick={() => void send()} disabled={sending || !text.trim()}>
              Надіслати
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
