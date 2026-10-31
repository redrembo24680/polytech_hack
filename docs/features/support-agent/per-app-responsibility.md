# Що робить кожен застосунок

| Застосунок | Відповідальність | Чого НЕ робить |
|---|---|---|
| support-agent/agent/ | LLM-цикл, системний промпт, tools, permission engine, апруви, події, метрики, FastAPI (порт 8000), оркестратор тріажу (`orchestrator.py`), емоції/суржик (`lingo.py`), голосовий webhook Vapi (`voice.py`), `POST /chat` для сайту (`chat_webhook.py`, в роботі), `MemoryDataSource` із `seed.json` і `HttpDataSource` до :8001 (в роботі), роздача `support-agent/web/` | Не зберігає дані між рестартами; не перевіряє автентифікацію; не веде реальні SMS |
| app/ (site/) | Платформа бронювань тіммейта (порт 8001): дані тенантів, HTTP API за контрактом спеки апки, адмінка; викликає `POST /chat` агента (в роботі) | Не перевіряє політику тенанта (це робить `support-agent/agent/policy.py`); лише цілісність даних. У цьому репо поки відсутній |
| support-agent/web/ | Демо-UI: чат клієнта зліва, copilot (події, апруви, метрики) справа | Не містить бізнес-логіки; не ходить до апки напряму, лише до API агента |
| support-agent/scripts/ | `smoke.py`: прогін сценаріїв A/B/C у консолі | Не є тестом; потребує `GEMINI_API_KEY` або `AGENT_PROVIDER=fake` |
| support-agent/tests/ | 218 pytest-тестів без мережі (policy, datasource, tools, agent loop, API, llm, orchestrator, lingo, voice, chat) | Не ходять у реальний LLM |
