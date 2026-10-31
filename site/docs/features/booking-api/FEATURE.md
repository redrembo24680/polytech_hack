# booking-api

HTTP JSON API мульти-тенант платформи бронювань (FastAPI + SQLAlchemy 2 + Postgres), `app/backend/booking/`.

Дає:
- CRUD: тенанти та політика, майстри та графік, послуги, клієнти, бронювання.
- Пошук вільних слотів `GET /api/tenants/{tid}/slots`.
- Дії підтримки за контрактом агента: reschedule, cancel, refund, waive-no-show, goodwill.
- Вихідні повідомлення (`/messages`) та тікети (`/tickets`).
- `POST /api/admin/reset` — повернення демо-даних до початкового стану; `GET /api/health`.

Усі сутності прив'язані до тенанта через шлях `/api/tenants/{tenant_id}/...`; чужа сутність у шляху дає 404.
Помилки: `{"error": code, "message": text}`; `not_found` 404, `invalid_state` 409, `slot_taken` 409, `validation` 422.
Апка перевіряє лише цілісність даних, політику (`agent_permissions`) не перевіряє.
