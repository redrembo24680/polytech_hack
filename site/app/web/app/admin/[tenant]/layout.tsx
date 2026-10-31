import { notFound } from "next/navigation";
import { api, ApiError } from "@/lib/api-core";
import type { Tenant } from "@/lib/types";
import { AdminNav } from "@/components/admin/AdminNav";
import { AgentApprovals } from "@/components/admin/AgentApprovals";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children, params }: LayoutProps<"/admin/[tenant]">) {
  const { tenant } = await params;
  let t: Tenant;
  try {
    t = await api.get<Tenant>(`/api/tenants/${tenant}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <AdminNav tenant={tenant} tenantName={t.name} />
      <div className="min-w-0 flex-1">
        <AgentApprovals tenant={tenant} />
        {children}
      </div>
    </div>
  );
}
