# Перетини з іншими фічами

## Порти
- Агент (API + фронт): `8000` (`uv run uvicorn agent.main:app --port 8000`).
- Апка тіммейта (`booking-platform`, `app/`): `8001`.

## Env-змінні
| Змінна | Призначення | Дефолт |
|---|---|---|
| `AGENT_PROVIDER` | `gemini` або `fake` (`fake` = на кожне повідомлення фіксована відповідь "Тестова відповідь", без tool-викликів) | `gemini` |
| `AGENT_MODEL` | модель Gemini API | `gemma-4-31b-it` |
| `GEMINI_API_KEY` | ключ з aistudio.google.com; без нього `make_client()` кидає `RuntimeError` | немає |
| `AGENT_SYSTEM_AS_PREFIX` | `1` = системний промпт іде префіксом у першому user-повідомленні, а не як `system_instruction` (обхід для моделей без підтримки system) | вимкнено |
| `APP_API_URL` | майбутнє: HTTP-контракт апки, напр. `http://localhost:8001`; у коді ще не читається | немає |
| `APP_MCP_URL` | майбутнє: MCP апки, напр. `http://localhost:8001/mcp`; у коді ще не читається | немає |

`.env` підхоплює `python-dotenv` у `make_client()`; шаблон у `.env.example`. Планований вибір DataSource: `APP_MCP_URL` -> Mcp, інакше `APP_API_URL` -> Http, інакше Memory. Зараз завжди `MemoryDataSource`.

## Контракт DataSource <-> платформа
Протокол `agent/datasource.py:DataSource` відповідає 1:1 контракту апки (спека апки, розділ 4): `get_tenant`, `get_client`, `list_clients`, `find_client_by_phone`, `list_client_bookings`, `get_booking`, `find_slots`, `reschedule`, `cancel`, `refund`, `waive_no_show`, `add_goodwill`, `send_message`, `create_ticket`.
- Імена MCP-tools апки: `get_tenant`, `get_client`, `find_client_by_phone`, `get_booking`, `find_slots`, `reschedule_booking`, `cancel_booking`, `refund_prepayment`, `waive_no_show_fee`, `add_goodwill`, `send_message`, `create_ticket`.
- Помилки апки `{"error": код, "message": ...}` з кодами `not_found`, `invalid_state`, `slot_taken`, `validation` мають перетворюватись на `DataError(code, message)`.
- Поле `by`: `agent` або `human:<ім'я>`; `forfeit_prepayment` передає агент, апка політику не перевіряє.
- `list_clients` і `list_client_bookings` (потрібні `GET /tenants/{id}` і `get_client_profile`) відсутні в таблиці контракту апки: це потрібно узгодити з тіммейтом (у HTTP-контракті є `GET /clients/{id}` із `bookings`, але немає списку клієнтів).
- Seed `agent/seed.json` має збігатися з сід-даними апки (клієнти `olena`, `max`, `ira` у `lumen`; `petro`, `anna` у `denta`).

## Інші перетини
- Фронт `web/` викликає лише API агента (той самий origin, CORS відкритий).
- Адмінка апки може брати чергу апрувів з `GET /tenants/{id}/approvals` і метрики з `/metrics`.
