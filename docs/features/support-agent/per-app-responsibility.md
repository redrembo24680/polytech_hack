# Що робить кожен застосунок

| Застосунок | Відповідальність | Чого НЕ робить |
|---|---|---|
| support-agent/agent/ | LLM-цикл, системний промпт, tools, permission engine, апруви, події, метрики, FastAPI (порт 8000), `MemoryDataSource` із `seed.json`, роздача `support-agent/web/` | Не зберігає дані між рестартами; не перевіряє автентифікацію; не веде реальні SMS |
| app/ | Платформа бронювань тіммейта (порт 8001): дані тенантів, HTTP/MCP API за контрактом спеки апки, адмінка | Не перевіряє політику тенанта (це робить `support-agent/agent/policy.py`); лише цілісність даних. У цьому репо поки відсутній |
| support-agent/web/ | Демо-UI: чат клієнта зліва, copilot (події, апруви, метрики) справа | Не містить бізнес-логіки; не ходить до апки напряму, лише до API агента |
| support-agent/scripts/ | `smoke.py`: прогін сценаріїв A/B/C у консолі | Не є тестом; потребує `GEMINI_API_KEY` або `AGENT_PROVIDER=fake` |
| support-agent/tests/ | 137 pytest-тестів без мережі (policy, datasource, tools, agent loop, API, llm) | Не ходять у реальний LLM |
