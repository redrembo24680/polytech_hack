import type { Metadata } from "next";
import { SupportChat } from "@/components/chat/SupportChat";

export const metadata: Metadata = { title: "Підтримка — чат" };

export default async function SupportPage(props: PageProps<"/b/[tenant]/support">) {
  const { tenant } = await props.params;
  const { embed } = await props.searchParams;
  return <SupportChat tenant={tenant} embed={embed === "1"} />;
}
