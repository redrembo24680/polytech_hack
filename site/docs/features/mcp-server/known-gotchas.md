# Відомі підводні камені

- Сервер не перевіряє політику та `agent_permissions` — це робота агента (API перевіряє лише цілісність).
- Помилки не є винятками: інструмент повертає звичайний текст `slot_taken: ...`, `invalid_state: ...`, `not_found: ...`, `validation: ...`, `api_unavailable: ...`. Агент має розпізнавати їх за префіксом.
- Datetime мають містити офсет; без офсету API відповідає `validation` (422). `date_to` у `find_slots` обмежує початок слота.
- `find_slots` приймає `date_from`/`date_to`, а в API це `from`/`to`.
- `refund_booking.amount` — ціле число гривень; більше за передоплату -> `validation`.
- Для HTTP-режиму в Docker потрібен запущений `backend`; у stdio-режимі `APP_API_URL` треба вказати вручну (за замовчуванням `http://localhost:8001`).
- Після `smoke.py` дані змінені: виконайте `curl -XPOST localhost:8001/api/admin/reset`.
- Прямий `http`-клієнт без MCP-обгортки не підійде: ендпоінт `/mcp` говорить протоколом MCP, а не REST.
