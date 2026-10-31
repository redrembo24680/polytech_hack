"use client";

import { useState } from "react";
import { mutate as globalMutate } from "swr";
import { api, ApiError, useApi } from "@/lib/api";
import type { Booking, Slot } from "@/lib/types";
import { formatDateTime, formatPrice } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { FEE_LABEL, PREPAYMENT_LABEL, STATUS_BADGE, STATUS_LABEL } from "./status";
import { SlotPicker } from "./SlotPicker";
import { Timeline } from "./Timeline";

type Mode = null | "reschedule" | "cancel" | "refund" | "waive" | "delete";
const BY = "human:admin";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-900">{children}</dd>
    </div>
  );
}

export function BookingCard({ tenant, bookingId, onClose }: { tenant: string; bookingId: string; onClose: () => void }) {
  const base = `/api/tenants/${tenant}/bookings/${bookingId}`;
  const { data: b, error, mutate } = useApi<Booking>(base, { refreshMs: 3000 });
  const toast = useToast();
  const [mode, setMode] = useState<Mode>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [forfeit, setForfeit] = useState(false);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [amount, setAmount] = useState("");

  function openMode(m: Mode) {
    setMode(m);
    setReason("");
    setForfeit(false);
    setSlot(null);
    setAmount(String(b?.prepayment.amount ?? ""));
  }

  async function run(fn: () => Promise<unknown>, okText: string, closeAfter = false) {
    setBusy(true);
    try {
      await fn();
      await mutate();
      await globalMutate((k) => typeof k === "string" && k.includes(`/tenants/${tenant}/bookings?`));
      toast.success(okText);
      setMode(null);
      if (closeAfter) onClose();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Щось пішло не так");
    } finally {
      setBusy(false);
    }
  }

  const setStatus = (status: "completed" | "no_show", text: string) =>
    run(() => api.patch(base, { status, by: BY }), text);

  function submit() {
    if (!b) return;
    switch (mode) {
      case "reschedule":
        if (!slot) return toast.error("Оберіть слот");
        return run(
          () => api.post(`${base}/reschedule`, { start: slot.start, staff_id: slot.staff_id, reason, by: BY, forfeit_prepayment: forfeit }),
          "Бронювання перенесено",
        );
      case "cancel":
        return run(() => api.post(`${base}/cancel`, { reason, by: BY, forfeit_prepayment: forfeit }), "Бронювання скасовано");
      case "refund": {
        const n = Number(amount);
        if (!Number.isInteger(n) || n <= 0) return toast.error("Вкажіть суму цілими гривнями");
        return run(() => api.post(`${base}/refund`, { amount: n, reason, by: BY }), "Передоплату повернено");
      }
      case "waive":
        return run(() => api.post(`${base}/waive-no-show`, { reason, by: BY }), "Штраф знято");
      case "delete":
        return run(() => api.del(base), "Бронювання видалено", true);
    }
  }

  const scheduled = b?.status === "scheduled";
  const titles: Record<Exclude<Mode, null>, string> = {
    reschedule: "Перенести", cancel: "Скасувати бронювання", refund: "Повернути передоплату",
    waive: "Зняти штраф", delete: "Видалити бронювання",
  };

  return (
    <Modal open onClose={onClose} title={b ? `Бронювання ${b.id}` : "Бронювання"} size="lg">
      {error && !b && <p className="text-sm text-red-600">{error.message}</p>}
      {!b && !error && <p className="text-sm text-slate-500">Завантаження…</p>}
      {b && (
        <div className="space-y-5">
          <dl className="divide-y divide-slate-100">
            <Row label="Клієнт">{b.client?.name ?? b.client_name} · {b.client?.phone}</Row>
            <Row label="Майстер">{b.staff?.name ?? b.staff_name}</Row>
            <Row label="Послуга">{b.service?.name ?? b.service_name}</Row>
            <Row label="Час">{formatDateTime(b.start)}</Row>
            <Row label="Статус"><Badge color={STATUS_BADGE[b.status]}>{STATUS_LABEL[b.status]}</Badge></Row>
            <Row label="Передоплата">{formatPrice(b.prepayment.amount)} · {PREPAYMENT_LABEL[b.prepayment.status]}</Row>
            <Row label="Штраф за неявку">{formatPrice(b.no_show_fee.amount)} · {FEE_LABEL[b.no_show_fee.status]}</Row>
          </dl>

          {mode === null ? (
            <div className="flex flex-wrap gap-2">
              {scheduled && (
                <>
                  <Button size="sm" variant="secondary" loading={busy} onClick={() => setStatus("completed", "Позначено «Виконано»")}>Позначити «Виконано»</Button>
                  <Button size="sm" variant="secondary" loading={busy} onClick={() => setStatus("no_show", "Позначено «Не прийшов»")}>Позначити «Не прийшов»</Button>
                  <Button size="sm" variant="secondary" onClick={() => openMode("reschedule")}>Перенести</Button>
                  <Button size="sm" variant="secondary" onClick={() => openMode("cancel")}>Скасувати</Button>
                </>
              )}
              {b.prepayment.status === "held" && (
                <Button size="sm" variant="secondary" onClick={() => openMode("refund")}>Повернути передоплату</Button>
              )}
              {b.no_show_fee.status === "charged" && (
                <Button size="sm" variant="secondary" onClick={() => openMode("waive")}>Зняти штраф</Button>
              )}
              <Button size="sm" variant="danger" onClick={() => openMode("delete")}>Видалити</Button>
            </div>
          ) : (
            <form
              className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3"
              onSubmit={(e) => { e.preventDefault(); submit(); }}
            >
              <h3 className="text-sm font-semibold text-slate-900">{titles[mode]}</h3>
              {mode === "reschedule" && (
                <SlotPicker tenant={tenant} serviceId={b.service_id} value={slot} onChange={setSlot} />
              )}
              {mode === "refund" && (
                <Input label="Сума, грн" type="number" min={1} max={b.prepayment.amount} value={amount} onChange={(e) => setAmount(e.target.value)} />
              )}
              {(mode === "reschedule" || mode === "cancel") && b.prepayment.status === "held" && (
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" checked={forfeit} onChange={(e) => setForfeit(e.target.checked)} />
                  Передоплата втрачається
                </label>
              )}
              {mode === "delete" ? (
                <p className="text-sm text-slate-700">Бронювання буде видалено безповоротно. Продовжити?</p>
              ) : (
                <Textarea label="Причина" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
              )}
              <div className="flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => setMode(null)} disabled={busy}>Назад</Button>
                <Button type="submit" size="sm" variant={mode === "delete" ? "danger" : "primary"} loading={busy}>
                  {mode === "delete" ? "Видалити" : "Підтвердити"}
                </Button>
              </div>
            </form>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Історія</h3>
            <Timeline history={b.history} />
          </section>
        </div>
      )}
    </Modal>
  );
}
