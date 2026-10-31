import type { Booking, Tenant } from "@/lib/types";
import { formatDateTime, formatPrice } from "@/lib/format";
import { LinkButton } from "@/components/ui/Button";

export function BookingConfirmation({
  tenant,
  booking,
  serviceName,
  staffName,
}: {
  tenant: Tenant;
  booking: Booking;
  serviceName: string;
  staffName: string;
}) {
  const rows: [string, string][] = [
    ["Дата і час", formatDateTime(booking.start, tenant.timezone)],
    ["Майстер", staffName],
    ["Послуга", serviceName],
    [
      "Передоплата",
      booking.prepayment.amount > 0 ? formatPrice(booking.prepayment.amount) : "не потрібна",
    ],
  ];
  return (
    <section className="mt-5 rounded-2xl border border-green-200 bg-white p-6 shadow-sm" role="status">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-green-100 text-xl text-green-700" aria-hidden>✓</span>
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Запис підтверджено</h2>
          <p className="text-sm text-slate-600">{tenant.name}</p>
        </div>
      </div>
      <dl className="mt-5 divide-y divide-slate-100 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-2.5">
            <dt className="text-slate-500">{k}</dt>
            <dd className="text-right font-medium text-slate-900">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-6">
        <LinkButton href={`/b/${tenant.id}`}>Повернутись на сторінку бізнесу</LinkButton>
      </div>
    </section>
  );
}
