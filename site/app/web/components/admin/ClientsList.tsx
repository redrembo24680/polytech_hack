"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import type { Client } from "@/lib/types";
import { formatPhone } from "@/lib/phone";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Table } from "@/components/ui/Table";
import { ClientForm } from "./ClientForm";

export function ClientsList({ tenant }: { tenant: string }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const path = `/api/tenants/${tenant}/clients${debounced ? `?q=${encodeURIComponent(debounced)}` : ""}`;
  const { data, error, isLoading, mutate } = useApi<Client[]>(path);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold text-slate-900">Клієнти</h1>
        <Button onClick={() => setCreating(true)}>Новий клієнт</Button>
      </div>
      <Input aria-label="Пошук" placeholder="Пошук за ім'ям або телефоном" value={q} onChange={(e) => setQ(e.target.value)} />
      {error && <p className="text-sm text-red-600">{error.message}</p>}
      <Table
        columns={[
          { key: "name", header: "Ім'я", render: (c) => <span className="font-medium text-slate-900">{c.name}</span> },
          { key: "phone", header: "Телефон", render: (c) => formatPhone(c.phone) },
          { key: "visits", header: "Візитів", render: (c) => c.visits_count },
          { key: "ns", header: "Неявок", render: (c) => (c.no_show_count > 0 ? <Badge color="red">{c.no_show_count}</Badge> : 0) },
          {
            key: "link",
            header: "",
            render: (c) => (
              <Link href={`/admin/${tenant}/clients/${c.id}`} className="text-accent-600 hover:underline">Профіль</Link>
            ),
          },
        ]}
        rows={data ?? []}
        rowKey={(c) => c.id}
        empty={isLoading ? "Завантаження…" : "Клієнтів не знайдено"}
      />
      <ClientForm tenant={tenant} open={creating} onClose={() => setCreating(false)} onSaved={() => mutate()} />
    </div>
  );
}
