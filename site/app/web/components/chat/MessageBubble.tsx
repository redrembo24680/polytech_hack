import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/cn";

const ROLE_LABEL: Record<ChatMessage["role"], string | null> = {
  client: null,
  agent: "AI-асистент",
  human: "Адміністратор",
};

function time(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ message, clientLabel }: { message: ChatMessage; clientLabel?: string }) {
  const mine = message.role === "client";
  const label = mine ? (clientLabel ?? null) : ROLE_LABEL[message.role];
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[85%] flex-col gap-1", mine ? "items-end" : "items-start")}>
        {label && (
          <span
            className={cn(
              "px-1 text-xs font-medium",
              message.role === "human" ? "text-amber-700" : "text-accent-700",
            )}
          >
            {label}
          </span>
        )}
        <div
          className={cn(
            "whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm leading-relaxed shadow-sm",
            mine && "rounded-br-md bg-accent-600 text-white",
            message.role === "agent" && "rounded-bl-md border border-slate-200 bg-white text-slate-900",
            message.role === "human" && "rounded-bl-md border border-amber-200 bg-amber-50 text-slate-900",
          )}
        >
          {message.text}
        </div>
        <span className="px-1 text-[11px] text-slate-400">{time(message.ts)}</span>
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex justify-start" role="status" aria-live="polite">
      <div className="flex flex-col items-start gap-1">
        <span className="px-1 text-xs font-medium text-accent-700">AI-асистент</span>
        <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-500 shadow-sm">
          <span className="flex gap-1" aria-hidden>
            {[0, 150, 300].map((d) => (
              <span
                key={d}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
                style={{ animationDelay: `${d}ms` }}
              />
            ))}
          </span>
          Агент друкує…
        </div>
      </div>
    </div>
  );
}
