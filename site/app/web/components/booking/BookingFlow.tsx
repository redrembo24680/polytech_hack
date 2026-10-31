"use client";

import { useMemo, useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";
import type { Booking, PublicTenant, Service, Slot, Staff } from "@/lib/types";
import { cn } from "@/lib/cn";
import { dayBoundary, dayLabel, formatPrice, formatDuration, formatTime, nextDays } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { BookingConfirmation } from "./BookingConfirmation";

const ANY = "any";

function StepTitle({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
      <span className="grid h-6 w-6 place-items-center rounded-full bg-accent-600 text-xs text-white">{n}</span>
      {children}
    </h2>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">{children}</section>;
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        "rounded-xl border px-4 py-3 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500",
        selected ? "border-accent-600 bg-accent-50 text-accent-700" : "border-slate-200 bg-white text-slate-800 hover:border-slate-300",
      )}
    >
      {children}
    </button>
  );
}

export function BookingFlow({ tenant, services, staff }: { tenant: PublicTenant; services: Service[]; staff: Staff[] }) {
  const toast = useToast();
  const tz = tenant.timezone;
  const days = useMemo(() => nextDays(7, tz), [tz]);

  const [serviceId, setServiceId] = useState<string | null>(null);
  const [staffChoice, setStaffChoice] = useState<string>(ANY);
  const [day, setDay] = useState<string>(days[0]);
  const [slotStart, setSlotStart] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; phone?: string; form?: string }>({});
  const [done, setDone] = useState<{ booking: Booking; serviceName: string; staffName: string } | null>(null);

  const service = services.find((s) => s.id === serviceId) ?? null;
  const eligibleStaff = staff.filter((m) => serviceId && m.service_ids.includes(serviceId));

  const nextKey = days[days.indexOf(day) + 1] ?? nextDays(2, tz, new Date(new Date(`${day}T12:00:00Z`).getTime() + 86400000))[0];
  const slotsPath = service
    ? `/api/tenants/${tenant.id}/slots?` +
      new URLSearchParams({
        service_id: service.id,
        from: dayBoundary(day, tz),
        to: dayBoundary(nextKey, tz),
        ...(staffChoice !== ANY ? { staff_id: staffChoice } : {}),
      }).toString()
    : null;
  const { data: slots, error: slotsError, isLoading, mutate } = useApi<Slot[]>(slotsPath);

  // One entry per start time; for "any" master the first free master is used.
  const times = useMemo(() => {
    const byStart = new Map<string, Slot>();
    for (const s of slots ?? []) if (!byStart.has(s.start)) byStart.set(s.start, s);
    return [...byStart.values()].sort((a, b) => a.start.localeCompare(b.start));
  }, [slots]);
  const chosen = times.find((s) => s.start === slotStart) ?? null;
  const chosenStaff = chosen ? staff.find((m) => m.id === chosen.staff_id) : null;

  const pickService = (id: string) => {
    setServiceId(id);
    setStaffChoice(ANY);
    setSlotStart(null);
  };

  const submit = async () => {
    if (submitting || !service || !chosen) return;
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Вкажіть ім'я";
    if (!phone.trim()) next.phone = "Вкажіть телефон";
    setErrors(next);
    if (next.name || next.phone) return;
    setSubmitting(true);
    try {
      const b = await api.post<Booking>(`/api/tenants/${tenant.id}/bookings`, {
        client: { name: name.trim(), phone: phone.trim() },
        service_id: service.id,
        staff_id: chosen.staff_id,
        start: chosen.start,
        by: "human:client",
      });
      setDone({ booking: b, serviceName: service.name, staffName: chosenStaff?.name ?? chosen.staff_name });
    } catch (e) {
      if (e instanceof ApiError && e.code === "slot_taken") {
        toast.error("Цей час щойно зайняли");
        setErrors({ form: "Цей час щойно зайняли. Оберіть інший час." });
        setSlotStart(null);
        await mutate();
      } else {
        setErrors({ form: e instanceof ApiError ? e.message : "Не вдалося створити запис" });
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return <BookingConfirmation tenant={tenant} {...done} />;
  }

  return (
    <div className="mt-5 space-y-4">
      <Card>
        <StepTitle n={1}>Послуга</StepTitle>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {services.map((s) => (
            <Choice key={s.id} selected={s.id === serviceId} onClick={() => pickService(s.id)}>
              <span className="block font-medium">{s.name}</span>
              <span className="text-slate-500">{formatDuration(s.duration_min)} · {formatPrice(s.price)}</span>
            </Choice>
          ))}
        </div>
      </Card>

      {service && (
        <Card>
          <StepTitle n={2}>Майстер</StepTitle>
          <div className="mt-3 flex flex-wrap gap-2">
            <Choice selected={staffChoice === ANY} onClick={() => { setStaffChoice(ANY); setSlotStart(null); }}>
              Будь-хто
            </Choice>
            {eligibleStaff.map((m) => (
              <Choice key={m.id} selected={staffChoice === m.id} onClick={() => { setStaffChoice(m.id); setSlotStart(null); }}>
                {m.name}
              </Choice>
            ))}
          </div>
        </Card>
      )}

      {service && (
        <Card>
          <StepTitle n={3}>Дата і час</StepTitle>
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1" role="group" aria-label="День">
            {days.map((d) => {
              const l = dayLabel(d);
              return (
                <button
                  key={d}
                  type="button"
                  aria-pressed={d === day}
                  onClick={() => { setDay(d); setSlotStart(null); }}
                  className={cn(
                    "flex w-16 shrink-0 flex-col items-center rounded-xl border px-2 py-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500",
                    d === day ? "border-accent-600 bg-accent-600 text-white" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300",
                  )}
                >
                  <span className="uppercase">{l.weekday}</span>
                  <span className="mt-0.5 font-semibold">{l.day}</span>
                </button>
              );
            })}
          </div>
          <div className="mt-4" aria-live="polite">
            {isLoading && <p className="text-sm text-slate-500">Завантаження часу…</p>}
            {slotsError && <p role="alert" className="text-sm text-red-700">{slotsError.message}</p>}
            {!isLoading && !slotsError && times.length === 0 && (
              <p className="text-sm text-slate-500">На цей день вільного часу немає. Спробуйте інший день.</p>
            )}
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
              {times.map((s) => (
                <button
                  key={s.start}
                  type="button"
                  aria-pressed={s.start === slotStart}
                  onClick={() => setSlotStart(s.start)}
                  className={cn(
                    "rounded-lg border py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500",
                    s.start === slotStart ? "border-accent-600 bg-accent-600 text-white" : "border-slate-200 bg-white text-slate-800 hover:border-accent-500",
                  )}
                >
                  {formatTime(s.start, tz)}
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}

      {service && chosen && (
        <Card>
          <StepTitle n={4}>Ваші дані</StepTitle>
          <form
            className="mt-3 space-y-3"
            noValidate
            onSubmit={(e) => { e.preventDefault(); void submit(); }}
          >
            <Input label="Ім'я" value={name} onChange={(e) => setName(e.target.value)} error={errors.name} autoComplete="name" />
            <Input
              label="Телефон"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              error={errors.phone}
              placeholder="+380 67 123 45 67"
              autoComplete="tel"
            />
            <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
              {service.name} · {chosenStaff?.name ?? chosen.staff_name} · {formatTime(chosen.start, tz)} · {formatPrice(service.price)}
              {tenant.policy.prepayment_required && " · потрібна передоплата"}
            </p>
            {errors.form && <p role="alert" className="text-sm text-red-700">{errors.form}</p>}
            <Button type="submit" size="lg" loading={submitting} className="w-full">Підтвердити запис</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
