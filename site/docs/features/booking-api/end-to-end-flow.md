# Наскрізний потік (сценарій агента)

1. `GET /api/tenants/lumen/clients/olena` — клієнт із бронюваннями (`bookings`, лічильники, `goodwill_exceptions`).
2. `GET /api/tenants/lumen/slots?service_id=lumen-styling&from=2026-11-03&to=2026-11-10` — вільні слоти (відсортовані).
3. `POST /api/tenants/lumen/bookings/b-olena-1/reschedule` `{start, staff_id?, reason, by, forfeit_prepayment}` → 200, бронювання
   з новим `start`/`end`, подією `rescheduled` у `history`.
4. Той самий слот для іншого запису → 409 `slot_taken`.
5. За потреби: `cancel`, `refund {amount, reason, by}`, `waive-no-show`, `POST clients/{id}/goodwill`,
   `POST /messages` (201), `POST /tickets` (201).

Дії над бронюванням повертають повне бронювання (з `client`, `staff`, `service`) зі статусом 200; goodwill — клієнта без `bookings`.
Кожна дія пише подію в `history` з `by` (`agent` або `human:<ім'я>`) і причиною. Покрито `tests/test_acceptance.py`.
