# Структура фронтенду

`support-agent/web/` — статичні файли без фреймворку, FastAPI монтує їх на `/` (`StaticFiles(html=True)`).

- `index.html` — одна сторінка: шапка (вибір тенанта `lumen`/`denta`, клієнта, кнопка "Нова сесія") і два стовпці.
- `app.js` — уся логіка, fetch + setInterval.
- `style.css` — стилі.

## Стовпці
- Чат клієнта: повідомлення, індикатор "агент думає…", картки (`renderCard`: `slots` як кнопки, `booking_summary` таблиця, `decision` блок; захисний: масиви перевіряються `Array.isArray`, відсутні поля пропускаються, передоплата показується як "500 грн, held"). Клік по слоту надсилає в чат "Обираю слот <start> (<майстер>)".
- Copilot адміністратора: метрики тенанта, список pending-апрувів (`approvalCard`: tool, args, причина, поле нотатки, "Схвалити"/"Відхилити", `by="Адміністратор"`), стрічка подій (`renderFeed`: thinking, tool_call з бейджем рішення, tool_result, approval_*; у `approval_decided` ім'я з `decided_by`).

## Звернення до бекенду (функція `api`)
`GET /tenants/{id}` (клієнти), `POST /sessions`, `POST /sessions/{sid}/messages`, `GET /sessions/{sid}/events?after=`, `GET /tenants/{id}/approvals?status=pending`, `POST /approvals/{id}/decide`, `GET /tenants/{id}/metrics`.

Події полінгуються кожні 700 мс, апруви кожні 1,5 с, метрики кожні 3 с; за `after=<id останньої події>`; дублі відсікає `state.seen`. Поки агент відповідає, поле вводу заблоковане (`setBusy`). Не перебудовує список апрувів, поки адмін пише нотатку.
