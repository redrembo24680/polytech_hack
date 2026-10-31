# Точки інтеграції

- `PATCH /api/tenants/{t}` {name, description, address, phone, instagram} — дані бізнесу.
- `PUT /api/tenants/{t}/policy` — повна Policy (завжди надсилається цілим об'єктом).
- `GET /support/conversations` (список із `client_name`, `last_message`), `GET …/{id}/messages?after=<ts>`, `POST …/{id}/reply {text, role:"human"}`, `PATCH …/{id} {status}`.
- `GET /tickets?status=`, `PATCH /tickets/{id} {status}`; `GET /messages`.
- Публічна сторінка `/b/[tenant]` показує `policyToText` (без `agent_permissions`) — тому зміна політики видна одразу.
- Клієнтський чат (`components/chat`) показує відповіді адміністратора з підписом «Адміністратор».
