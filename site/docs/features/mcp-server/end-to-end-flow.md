# Наскрізний потік

1. Агент підключається до `http://localhost:8002/mcp` (або stdio) і отримує список із 12 інструментів та їхні описи.
2. `get_tenant` -> політика бізнесу; `find_client_by_phone` -> клієнт; `get_booking` -> запис.
3. Агент сам перевіряє політику та `agent_permissions`.
4. Для переносу: `find_slots(date_from, date_to)` -> `reschedule_booking(start, reason, forfeit_prepayment)`.
5. Інструмент робить HTTP-запит до `APP_API_URL` через спільний `httpx.AsyncClient`. API валідує цілісність, змінює дані й дописує подію в `history` з `by="agent"`.
6. Успіх -> JSON; 4xx -> рядок `slot_taken: ...`; мережа недоступна -> `api_unavailable: ...`.
7. Агент пише клієнтові (`send_message`) або передає людині (`create_ticket`).

Перевірка наживо: `cd site/app/mcp && uv run python scripts/smoke.py` (потім `curl -XPOST localhost:8001/api/admin/reset`).
