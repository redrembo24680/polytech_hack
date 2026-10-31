import { BookingWeek } from "@/components/admin/BookingWeek";

export default async function AdminBookingsPage({ params }: PageProps<"/admin/[tenant]">) {
  const { tenant } = await params;
  return <BookingWeek tenant={tenant} />;
}
