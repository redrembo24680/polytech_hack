import { ServicesList } from "@/components/admin/ServicesList";

export default async function ServicesPage({ params }: PageProps<"/admin/[tenant]/services">) {
  const { tenant } = await params;
  return <ServicesList tenant={tenant} />;
}
