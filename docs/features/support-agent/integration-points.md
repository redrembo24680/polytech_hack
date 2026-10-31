# Перетини з іншими фічами

## Порти
- Агент (API + фронт): `8000` (`uv run uvicorn agent.main:app --port 8000`).
- Апка тіммейта (`booking-platform`, `app/`): `8001`.

## Env-змінні
| Змінна | Призначення | Дефолт |
|---|---|---|
| `AGENT_PROVIDER` | `gemini`, `anthropic` (Claude), `openai_compat` (псевдонім `ollama`) або `fake` (`fake` = на кожне повідомлення фіксована відповідь "Тестова відповідь", без tool-викликів) | `gemini` |
| `AGENT_MODEL` | модель Gemini API / Anthropic (`claude-sonnet-5-5` для `anthropic`) або тег локальної моделі (для `openai_compat`) | `gemma-4-31b-it` (для `openai_compat`: `gemma4`) |
| `OPENAI_BASE_URL` | база OpenAI-сумісного сервера (`POST {base}/chat/completions`), лише для `openai_compat`/`ollama` | `http://localhost:11434/v1` |
| `OPENAI_API_KEY` | ключ для OpenAI-сумісного сервера (Ollama його ігнорує) | `ollama` |
| `GEMINI_API_KEY` | ключ з aistudio.google.com; без нього `make_client()` кидає `RuntimeError` | немає |
| `ANTHROPIC_API_KEY` | ключ Anthropic API, лише для `anthropic`; без нього `make_client()` кидає `RuntimeError` | немає |
| `AGENT_SYSTEM_AS_PREFIX` | `1` = системний промпт іде префіксом у першому user-повідомленні, а не як `system_instruction` (обхід для моделей без підтримки system) | вимкнено |
| `APP_API_URL` | майбутнє: HTTP-контракт апки, напр. `http://localhost:8001`; у коді ще не читається | немає |
| `APP_MCP_URL` | майбутнє: MCP апки, напр. `http://localhost:8001/mcp`; у коді ще не читається | немає |

`.env` підхоплює `python-dotenv` у `make_client()`; шаблон у `support-agent/.env.example`. Планований вибір DataSource: `APP_MCP_URL` -> Mcp, інакше `APP_API_URL` -> Http, інакше Memory. Зараз завжди `MemoryDataSource`.

## Контракт DataSource <-> платформа
Протокол `support-agent/agent/datasource.py:DataSource` відповідає 1:1 контракту апки (спека апки, розділ 4): `get_tenant`, `get_client`, `list_clients`, `find_client_by_phone`, `list_client_bookings`, `get_booking`, `find_slots`, `reschedule`, `cancel`, `refund`, `waive_no_show`, `add_goodwill`, `send_message`, `create_ticket`.
- Імена MCP-tools апки: `get_tenant`, `get_client`, `find_client_by_phone`, `get_booking`, `find_slots`, `reschedule_booking`, `cancel_booking`, `refund_prepayment`, `waive_no_show_fee`, `add_goodwill`, `send_message`, `create_ticket`.
- Помилки апки `{"error": код, "message": ...}` з кодами `not_found`, `invalid_state`, `slot_taken`, `validation` мають перетворюватись на `DataError(code, message)`.
- Поле `by`: `agent` або `human:<ім'я>`; `forfeit_prepayment` передає агент, апка політику не перевіряє.
- `list_clients` і `list_client_bookings` (потрібні `GET /tenants/{id}` і `get_client_profile`) відсутні в таблиці контракту апки: це потрібно узгодити з тіммейтом (у HTTP-контракті є `GET /clients/{id}` із `bookings`, але немає списку клієнтів).
- Seed `support-agent/agent/seed.json` має збігатися з сід-даними апки (клієнти `olena`, `max`, `ira` у `lumen`; `petro`, `anna` у `denta`).

## Інші перетини
- Фронт `support-agent/web/` викликає лише API агента (той самий origin, CORS відкритий).
- Адмінка апки може брати чергу апрувів з `GET /tenants/{id}/approvals` і метрики з `/metrics`.

## Gemma 4 / Ollama / Gemini API (оркестратор)
`ORCHESTRATOR_PROVIDER=gemini`: `langchain-google-genai` `ChatGoogleGenerativeAI` (`GEMINI_API_KEY`, модель `gemma-4-31b-it`, безкоштовно); без ключа оркестратор вимкнено. За замовчуванням (`ollama`):
`langchain-ollama` `ChatOllama` -> `ORCHESTRATOR_BASE_URL` (за замовчуванням `http://localhost:11434`), модель `ORCHESTRATOR_MODEL`. Окремо від провайдера воркера (`AGENT_PROVIDER`). Оркестратор не має доступу до tools і даних апки, лише до `rules_text` і короткого опису клієнта.

## Claude Sonnet (оркестратор) і Gemma 4 (відповідач)
Оркестратор за замовчуванням: `langchain-anthropic` `ChatAnthropic` (`ORCHESTRATOR_MODEL=claude-sonnet-5-5`, `ANTHROPIC_API_KEY`, `temperature=0`, `max_tokens=512`); альтернативи `ORCHESTRATOR_PROVIDER=ollama|gemini` (описано вище). Відповідач `Answerer`: `ANSWERER=on|off`, `ANSWERER_PROVIDER=ollama` (за замовчуванням, `ANSWERER_MODEL=gemma4:12b`, `ANSWERER_BASE_URL=http://localhost:11434`) або `gemini` (`gemma-4-31b-it`, `GEMINI_API_KEY`; без ключа відповідача немає). Створення клієнтів не робить мережевих викликів.

## Vapi (телефонія)

- Vapi -> наш сервер: `POST /voice/tools` (server URL асистента). Тіло: `message.type="tool-calls"`, `message.toolCallList[]` (`id`, `function.name`, `function.arguments`), `message.call.customer.number`. Відповідь: `{"results":[{"toolCallId","result":"<рядок>"}]}`, HTTP 200.
- Наш сервер -> Vapi: `scripts/vapi_setup.py` (`POST/PATCH /assistant`, `POST /phone-number`). Докс: https://docs.vapi.ai/tools/custom-tools
