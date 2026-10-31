"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApi } from "@/lib/api";
import type { Ticket } from "@/lib/types";
import { cn } from "@/lib/cn";
import { ResetButton } from "./ResetButton";

const ITEMS = [
  { href: "", label: "Бронювання" },
  { href: "/clients", label: "Клієнти" },
  { href: "/staff", label: "Майстри" },
  { href: "/services", label: "Послуги" },
  { href: "/settings", label: "Налаштування" },
  { href: "/support", label: "Підтримка" },
];

export function AdminNav({ tenant, tenantName }: { tenant: string; tenantName: string }) {
  const pathname = usePathname();
  const base = `/admin/${tenant}`;
  const { data: open } = useApi<Ticket[]>(`/api/tenants/${tenant}/tickets?status=open`, { refreshMs: 5000 });
  const count = open?.length ?? 0;

  return (
    <aside className="flex shrink-0 flex-col gap-4 md:w-52">
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Адмін-панель</div>
        <div className="text-lg font-semibold text-slate-900">{tenantName}</div>
      </div>
      <nav className="flex gap-1 overflow-x-auto md:flex-col">
        {ITEMS.map((it) => {
          const href = base + it.href;
          const active = it.href === "" ? pathname === base : pathname.startsWith(href);
          return (
            <Link
              key={it.href}
              href={href}
              className={cn(
                "flex items-center justify-between gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium",
                active ? "bg-accent-50 text-accent-700" : "text-slate-700 hover:bg-slate-100",
              )}
            >
              {it.label}
              {it.href === "/support" && count > 0 && (
                <span className="rounded-full bg-red-500 px-1.5 text-xs text-white" aria-label={`Відкритих тікетів: ${count}`}>
                  {count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="md:mt-auto"><ResetButton /></div>
    </aside>
  );
}
