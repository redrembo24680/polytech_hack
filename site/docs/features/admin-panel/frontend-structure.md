# Структура фронтенда (`app/web`)

- `app/admin/[tenant]/layout.tsx` — серверний, `force-dynamic`, 404 -> `notFound()`; рендерить `AdminNav` з назвою бізнесу.
- `components/admin/AdminNav` (меню, бейдж відкритих тікетів, `ResetButton`), `status.ts` (підписи статусів і подій, `byLabel`).
- Бронювання: `BookingWeek`, `BookingCard`, `BookingForm`, `SlotPicker`, `Timeline`; `lib/week.ts`.
- CRUD: `ClientsList/ClientProfile/ClientForm`, `StaffList/StaffForm/ScheduleEditor`, `ServicesList/ServiceForm`; `lib/phone.ts`, `lib/schedule.ts`.
- Налаштування: `SettingsPanel({tenant})` (форма даних бізнесу + `PolicyForm`), `PolicyForm({tenant, policy, onSaved?})` з живим переглядом `policyToText`; після збереження назви — `router.refresh()`.
- Підтримка: `SupportInbox({tenant})` (вкладки), `ConversationList({tenant, selectedId, onSelect})`, `ConversationView({tenant, conversationId})` (опитування з `?after=`, дедуплікація за id, використовує `MessageBubble` із `components/chat`), `TicketList({tenant})`, `MessageLog({tenant})`.
