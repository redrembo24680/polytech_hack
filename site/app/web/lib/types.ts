// TS types mirroring the booking API JSON (see site/docs/features/booking-api).
// All ids are strings. Datetimes are ISO 8601 strings with offset (Europe/Kyiv). Money is whole UAH.

export type TenantKind = "salon" | "clinic";
export const TENANT_KIND_LABEL: Record<TenantKind, string> = {
  salon: "Салон",
  clinic: "Клініка",
};

export type Gate = "auto" | "approval" | "forbidden";
export type AutoGate = "auto" | "approval";

export interface AgentPermissions {
  reschedule: AutoGate;
  cancel: AutoGate;
  refund: "auto_under_limit" | "approval" | "forbidden";
  refund_auto_limit: number;
  goodwill_exception: Gate;
  goodwill_per_client_per_180d: number;
  goodwill_requires_zero_no_shows: boolean;
  waive_no_show_fee: Gate;
}

export interface Policy {
  cancellation_window_hours: number;
  late_change_forfeits_prepayment: boolean;
  no_show_fee: number;
  prepayment_required: boolean;
  agent_permissions: AgentPermissions;
}

export interface Tenant {
  id: string;
  name: string;
  kind: TenantKind;
  timezone: string;
  description: string;
  address: string;
  phone: string;
  instagram: string;
  policy: Policy;
}

export interface ScheduleRow {
  weekday: number; // 0 = Monday
  start: string; // "HH:MM"
  end: string; // "HH:MM"
}

export interface Staff {
  id: string;
  tenant_id: string;
  name: string;
  service_ids: string[];
  schedule: ScheduleRow[];
}

export interface Service {
  id: string;
  tenant_id: string;
  name: string;
  duration_min: number;
  price: number;
}

export interface GoodwillException {
  date: string; // YYYY-MM-DD
  booking_id: string;
  reason: string;
}

export interface Client {
  id: string;
  tenant_id: string;
  name: string;
  phone: string; // digits only, e.g. 380671234501
  visits_count: number;
  no_show_count: number;
  goodwill_exceptions: GoodwillException[];
  notes: string;
  /** Only on GET /clients/{id} */
  bookings?: Booking[];
}

export type BookingStatus = "scheduled" | "completed" | "cancelled" | "no_show";
export type PrepaymentStatus = "held" | "refunded" | "forfeited" | "none";
export type NoShowFeeStatus = "charged" | "waived" | "none";

export interface BookingEvent {
  ts: string;
  event: string; // created, prepayment_held, rescheduled, cancelled, refunded, no_show_waived, goodwill, completed ...
  by: string; // "agent" | "human:<name>"
  note: string;
}

export interface Booking {
  id: string;
  tenant_id: string;
  client_id: string;
  staff_id: string;
  service_id: string;
  start: string;
  end: string;
  status: BookingStatus;
  prepayment: { amount: number; status: PrepaymentStatus };
  no_show_fee: { amount: number; status: NoShowFeeStatus };
  history: BookingEvent[];
  notes: string;
  /** Present on GET /bookings list */
  client_name?: string;
  staff_name?: string;
  service_name?: string;
  /** Present on GET /bookings/{id} */
  client?: Client;
  staff?: Staff;
  service?: Service;
}

export interface Slot {
  staff_id: string;
  staff_name: string;
  start: string;
  end: string;
}

export type Channel = "chat" | "sms";
export interface OutgoingMessage {
  id: string;
  tenant_id: string;
  client_id: string;
  channel: Channel;
  text: string;
  ts: string;
}

export type Priority = "low" | "normal" | "high" | "urgent";
export type TicketStatus = "open" | "closed";
export interface Ticket {
  id: string;
  tenant_id: string;
  client_id: string;
  summary: string;
  priority: Priority;
  status: TicketStatus;
  ts: string;
}

export type ConversationStatus = "open" | "closed";
export type ChatRole = "client" | "agent" | "human";

export interface Conversation {
  id: string;
  tenant_id: string;
  client_id: string | null;
  status: ConversationStatus;
  created_at: string;
  visitor_name: string | null;
  visitor_phone: string | null;
  /** Only in the list endpoint (inbox) */
  client_name?: string | null;
  last_message?: { text: string; role: ChatRole; ts: string } | null;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: ChatRole;
  text: string;
  ts: string;
}

/** Narrow tenant shape safe to send to client components (no agent_permissions). */
export interface PublicTenant {
  id: string;
  name: string;
  timezone: string;
  policy: { prepayment_required: boolean };
}

export function toPublicTenant(t: Tenant): PublicTenant {
  return {
    id: t.id,
    name: t.name,
    timezone: t.timezone,
    policy: { prepayment_required: t.policy.prepayment_required },
  };
}
