import { SettingsPanel } from "@/components/admin/SettingsPanel";

export default async function SettingsPage({ params }: PageProps<"/admin/[tenant]/settings">) {
  const { tenant } = await params;
  return <SettingsPanel tenant={tenant} />;
}
