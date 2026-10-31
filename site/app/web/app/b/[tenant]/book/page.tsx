import { notFound } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api-core";
import type { Service, Staff, Tenant } from "@/lib/types";
import { BookingFlow } from "@/components/booking/BookingFlow";

export const dynamic = "force-dynamic";

export default async function BookPage(props: PageProps<"/b/[tenant]/book">) {
  const { tenant: id } = await props.params;
  let data: { tenant: Tenant; services: Service[]; staff: Staff[] };
  try {
    const opts = { cache: "no-store" } as const;
    const [tenant, services, staff] = await Promise.all([
      api.get<Tenant>(`/api/tenants/${id}`, opts),
      api.get<Service[]>(`/api/tenants/${id}/services`, opts),
      api.get<Staff[]>(`/api/tenants/${id}/staff`, opts),
    ]);
    data = { tenant, services, staff };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return (
    <div className="mx-auto max-w-2xl">
      <Link href={`/b/${id}`} className="text-sm text-accent-700 hover:underline">← {data.tenant.name}</Link>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">Онлайн-запис</h1>
      <BookingFlow {...data} />
    </div>
  );
}
