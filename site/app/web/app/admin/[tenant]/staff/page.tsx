import { StaffList } from "@/components/admin/StaffList";

export default async function StaffPage({ params }: PageProps<"/admin/[tenant]/staff">) {
  const { tenant } = await params;
  return <StaffList tenant={tenant} />;
}
