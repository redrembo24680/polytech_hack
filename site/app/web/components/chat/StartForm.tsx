"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export function StartForm({
  onStart,
  busy,
  error,
}: {
  onStart: (name: string, phone: string) => void;
  busy: boolean;
  error: string | null;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [touched, setTouched] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!name.trim() || !phone.trim()) return;
    onStart(name.trim(), phone.trim());
  }

  return (
    <form onSubmit={submit} className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 p-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Чат підтримки</h2>
        <p className="mt-1 text-sm text-slate-500">
          Вкажіть ім&apos;я та телефон — за номером асистент знайде ваші записи.
        </p>
      </div>
      <Input
        label="Ім'я"
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoComplete="name"
        error={touched && !name.trim() ? "Вкажіть ім'я" : undefined}
      />
      <Input
        label="Телефон"
        type="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        autoComplete="tel"
        placeholder="+380 67 123 45 01"
        error={touched && !phone.trim() ? "Вкажіть телефон" : undefined}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <Button type="submit" loading={busy} size="lg">
        Почати чат
      </Button>
    </form>
  );
}
