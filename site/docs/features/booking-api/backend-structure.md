# Структура бекенда (`app/backend/booking/`)

- `main.py` — `create_app()`, CORS, обробники помилок, старт: `create_all` + сід, якщо таблиця `tenants` порожня.
- `models.py` — таблиці; `add_event()` пише подію бронювання (`history`).
- `schemas.py` — вихідні форми: `booking_out`, `client_out`, `message_out`, `ticket_out`, `iso()`; типи-літерали.
- `errors.py` — `ApiError(code, message, status)` і обробники (в т.ч. 422 з `RequestValidationError`).
- `timeparse.py` — `parse_when`: дата або datetime із офсетом, інакше 422.
- `phone.py` — `normalize_phone`; `clock.py` — `now()` (тести підміняють); `ids.py` — `new_id(prefix)`; `seed.py` — сід і `reset`.
- `routers/` — `tenants`, `staff`, `services`, `clients`, `slots`, `bookings` (CRUD), `actions` (reschedule/cancel/refund/
  waive-no-show/goodwill), `messages_tickets`, `admin` (reset), `deps` (`get_tenant_or_404`, `get_or_404`: чужий тенант -> 404).
- `services/bookings.py` — `is_slot_free` (єдине джерело істини про зайнятість), `create_booking`, `mark_status`.
  `services/slots.py` — генерація вільних слотів.

Правила цілісності дій (`routers/actions.py`):
- reschedule/cancel лише для `scheduled`, інакше 409 `invalid_state`. Reschedule: `staff_id` має надавати послугу (інакше 422);
  `end = start + тривалість послуги`; перевірка `is_slot_free(..., exclude_booking_id)` -> 409 `slot_taken`.
  `forfeit_prepayment=true` переводить передоплату `held` -> `forfeited` (для reschedule і cancel).
- refund: передоплата має бути `held` (409), `0 < amount <= prepayment.amount` (422); статус -> `refunded`.
- waive-no-show: `status == no_show` і штраф `charged` (409); -> `waived`.
- goodwill: бронювання має належати цьому клієнту (інакше 404); додає `GoodwillException` і подію `goodwill`.
- messages: `channel` `chat|sms` (за замовчуванням `chat`); tickets: `priority` за замовчуванням `normal`, статус `open|closed`.
  `client_id` має належати тенанту (404).
