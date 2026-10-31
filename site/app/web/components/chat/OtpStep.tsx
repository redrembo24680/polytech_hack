"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

/** "+380671234501" -> "+380•••4501" (all but the last 4 digits hidden). */
export function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.length <= 4) return phone;
  const prefix = phone.trim().startsWith("+") ? "+" : "";
  const head = digits.slice(0, Math.min(3, digits.length - 4));
  return `${prefix}${head}•••${digits.slice(-4)}`;
}

export function OtpStep({
  phone,
  expected,
  onVerified,
  onResend,
  onCancel,
}: {
  phone: string;
  expected: string;
  onVerified: () => void;
  onResend: () => Promise<void>;
  onCancel: () => void;
}) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (code.trim() === expected) onVerified();
    else setError("Код не збігається");
  }

  async function resend() {
    setError(null);
    setCode("");
    await onResend();
    setResent(true);
  }

  return (
    <form onSubmit={submit} className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 p-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Підтвердження номера</h2>
        <p className="mt-1 text-sm text-slate-500">
          Ми надіслали SMS із кодом підтвердження на номер {maskPhone(phone)}
        </p>
      </div>
      <Input
        aria-label="Код з SMS"
        value={code}
        onChange={(e) => {
          setCode(e.target.value.replace(/\D/g, "").slice(0, 4));
          setError(null);
        }}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={4}
        placeholder="••••"
        autoFocus
        error={error ?? undefined}
      />
      <Button type="submit" size="lg" disabled={code.length < 4}>
        Підтвердити
      </Button>
      <div className="flex items-center justify-between text-sm">
        <button type="button" onClick={() => void resend()} className="text-accent-600 hover:underline">
          Надіслати ще раз
        </button>
        {resent && <span className="text-slate-500">Код надіслано повторно</span>}
        <button type="button" onClick={onCancel} className="text-slate-500 hover:underline">
          Назад
        </button>
      </div>
    </form>
  );
}
