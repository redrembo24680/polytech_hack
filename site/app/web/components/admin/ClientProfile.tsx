"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError, useApi } from "@/lib/api";
import type { Client, Service, Staff } from "@/lib/types";
import { formatDateTime, formatPrice } from "@/lib/format";
import { formatPhone } from "@/lib/phone";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { BookingCard } from "./BookingCard";
import { ClientForm } from "./ClientForm";
import { STATUS_BADGE, STATUS_LABEL } from "./status";

export function ClientProfile({ tenant, clientId }: { tenant: string; clientId: string }) {
  const base = `/api/tenants/${tenant}/clients/${clientId}`;
  const { data: c, error, mutate } = useApi<Client>(base);
  const { data: services } = useApi<Service[]>(`/api/tenants/${tenant}/services`);
  const { data: staff } = useApi<Staff[]>(`/api/tenants/${tenant}/staff`);
  const toast = useToast();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const [openBooking, setOpenBooking] = useState<string | null>(null);
  const [notes, setNotes] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (error) return <p className="text-red-600">{error.message}</p>;
  if (!c) return <p className="text-slate-500">Завантаження…</p>;

  const svc = (id: string) => services?.find((s) => s.id === id)?.name ?? id;
  const st = (id: string) => staff?.find((s) => s.id === id)?.name ?? id;
  const bookings = [...(c.bookings ?? [])].sort((a, b) => b.start.localeCompare(a.start));
  const draft = notes ?? c.notes;

  async function saveNotes() {
    setBusy(true);
    try {
      await api.patch(base, { notes: draft });
      await mutate();
      setNotes(null);
      toast.success("Нотатки збережено");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Помилка");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.del(base);
      toast.success("Клієнта видалено");
      router.push(`/admin/${tenant}/clients`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) toast.error("Є майбутні бронювання");
      else toast.error(e instanceof ApiError ? e.message : "Помилка");
      setConfirmDel(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link href={`/admin/${tenant}/clients`} className="text-sm text-accent-600 hover:underline">← Усі клієнти</Link>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{c.name}</h1>
          <p className="text-slate-600">{formatPhone(c.phone)}</p>
          <div className="mt-2 flex gap-2">
            <Badge color="green">Візитів: {c.visits_count}</Badge>
            <Badge color={c.no_show_count > 0 ? "red" : "gray"}>Неявок: {c.no_show_count}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEditing(true)}>Редагувати</Button>
          <Button variant="danger" onClick={() => setConfirmDel(true)}>Видалити</Button>
        </div>
      </header>

      <section className="space-y-2">
        <h2 className="font-semibold text-slate-900">Нотатки</h2>
        <Textarea aria-label="Нотатки" value={draft} onChange={(e) => setNotes(e.target.value)} />
        {notes !== null && notes !== c.notes && (
          <Button size="sm" loading={busy} onClick={saveNotes}>Зберегти нотатки</Button>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold text-slate-900">Винятки з доброї волі</h2>
        {c.goodwill_exceptions.length === 0 ? (
          <p className="text-sm text-slate-500">Немає</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {c.goodwill_exceptions.map((g) => (
              <li key={g.booking_id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <span className="font-medium">{g.date}</span> · {g.booking_id} · {g.reason}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold text-slate-900">Бронювання</h2>
        {bookings.length === 0 && <p className="text-sm text-slate-500">Немає бронювань</p>}
        <ul className="space-y-2">
          {bookings.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => setOpenBooking(b.id)}
                className="flex w-full flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-sm hover:border-accent-500"
              >
                <span>
                  <span className="font-medium text-slate-900">{formatDateTime(b.start)}</span>
                  <span className="text-slate-600"> · {svc(b.service_id)} · {st(b.staff_id)}</span>
                </span>
                <span className="flex items-center gap-2">
                  {b.prepayment.status === "held" && <span className="text-xs text-slate-500">передоплата {formatPrice(b.prepayment.amount)}</span>}
                  <Badge color={STATUS_BADGE[b.status]}>{STATUS_LABEL[b.status]}</Badge>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {openBooking && (
        <BookingCard tenant={tenant} bookingId={openBooking} onClose={() => { setOpenBooking(null); mutate(); }} />
      )}
      <ClientForm tenant={tenant} client={c} open={editing} onClose={() => setEditing(false)} onSaved={() => mutate()} />
      <Modal
        open={confirmDel}
        onClose={() => setConfirmDel(false)}
        title="Видалити клієнта?"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirmDel(false)}>Скасувати</Button>
            <Button variant="danger" loading={busy} onClick={remove}>Видалити</Button>
          </div>
        }
      >
        <p className="text-sm text-slate-700">Клієнта «{c.name}» буде видалено.</p>
      </Modal>
    </div>
  );
}
