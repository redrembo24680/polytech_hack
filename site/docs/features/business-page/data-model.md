# Модель даних

Власних таблиць немає. Використовуються типи з `lib/types.ts`: `Tenant` (+ `Policy`), `Service`, `Staff`, `Slot`, `Booking`.

- `Policy` -> `policyToText`: `cancellation_window_hours`, `late_change_forfeits_prepayment`, `no_show_fee`, `prepayment_required`. Рядки у фіксованому порядку: умова скасування, штраф за неявку (якщо > 0), передоплата (якщо потрібна). `agent_permissions` ігнорується.
- Запит створення бронювання: `{client:{name,phone}, service_id, staff_id, start (ISO з офсетом), by}`.
- Для підтвердження використовуються `booking.start` і `booking.prepayment.amount`.
