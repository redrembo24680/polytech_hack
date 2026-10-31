import { ClientProfile } from "@/components/admin/ClientProfile";

export default async function ClientPage({ params }: PageProps<"/admin/[tenant]/clients/[id]">) {
  const { tenant, id } = await params;
  return <ClientProfile tenant={tenant} clientId={id} />;
}
