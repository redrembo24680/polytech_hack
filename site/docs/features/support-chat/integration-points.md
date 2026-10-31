# Точки інтеграції: контракт агента (для тіммейта)

Змінна `AGENT_URL` (напр. `http://host.docker.internal:9000`; у `site/.env`, передається в compose як `AGENT_URL: ${AGENT_URL:-}`). Після зміни: `docker compose up -d backend`.

## Запит бекенду до агента
`POST {AGENT_URL}/chat`, `Content-Type: application/json`, **таймаут 60 с**:
```json
{
  "tenant_id": "lumen",
  "conversation_id": "conv-1a2b3c",
  "client_id": "olena",
  "messages": [
    {"role": "client", "text": "Хочу скасувати запис на завтра", "ts": "2026-10-31T14:32:53.854535+02:00"},
    {"role": "agent", "text": "Підкажіть, будь ласка, час запису", "ts": "2026-10-31T14:33:02.100000+02:00"},
    {"role": "client", "text": "О 15:00", "ts": "2026-10-31T14:33:20.000000+02:00"}
  ]
}
```
`client_id` може бути `null` (телефон не знайдено серед клієнтів тенанта). `messages` — повна історія, від старих до нових; `role` ∈ `client|agent|human`.

## Відповідь агента
```json
{"reply": "Запис скасовано, передоплату повернуто."}
```
- `reply` — непорожній рядок -> зберігається як `role=agent`.
- `reply` відсутній / `null` / порожній -> повідомлення не створюється (агент відповість пізніше асинхронно).

## Заглушки (тексти точні)
- `AGENT_URL` не задано: «Агент підтримки ще не підключений».
- Помилка мережі, таймаут 60 с, не-2xx, невалідний JSON: «Агент тимчасово недоступний, адміністратор відповість найближчим часом».

## Асинхронні відповіді
- `POST /api/tenants/{t}/support/conversations/{id}/reply` `{"text": "...", "role": "agent"}` (`role`: `agent` або `human`) -> 201 повідомлення. Закрита розмова -> 409.
- `POST /api/tenants/{t}/messages` з `channel: "chat"` — потрапляє в останню відкриту розмову клієнта (`role=agent`).
Клієнтська сторінка підхоплює їх протягом ~2 с.

## Перевірка без справжнього агента
`cd app/backend && uv run uvicorn scripts.echo_agent:app --port 9000` -> `AGENT_URL=http://host.docker.internal:9000`; відповідь: `echo: <останній текст клієнта>`.
