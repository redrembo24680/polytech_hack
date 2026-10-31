import { SupportInbox } from "@/components/admin/SupportInbox";

export default async function SupportPage({ params }: PageProps<"/admin/[tenant]/support">) {
  const { tenant } = await params;
  return <SupportInbox tenant={tenant} />;
}
