import { ClientsList } from "@/components/admin/ClientsList";

export default async function ClientsPage({ params }: PageProps<"/admin/[tenant]/clients">) {
  const { tenant } = await params;
  return <ClientsList tenant={tenant} />;
}
