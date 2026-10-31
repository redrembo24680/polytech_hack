# Модель даних

Адмінка власних таблиць не має. Використовує: Tenant (+Policy з `agent_permissions`), Booking/BookingEvent, Client, Staff, Service, Ticket (`priority`: low/normal/high/urgent; `status`: open/closed), OutgoingMessage (`channel`: chat/sms), Conversation (`status`: open/closed) і ChatMessage (`role`: client/agent/human). Типи — `app/web/lib/types.ts`.

`agent_permissions`: `reschedule`, `cancel` (auto|approval); `refund` (auto_under_limit|approval|forbidden) + `refund_auto_limit` (грн); `goodwill_exception`, `waive_no_show_fee` (auto|approval|forbidden); `goodwill_per_client_per_180d`; `goodwill_requires_zero_no_shows`.
