# Пітч (3 хв) і текст для сабмішну

Івент: PolyTech Code Fest / Hacktoberfest Hack Day Lviv (MLH). Челенджі: **Best Use of Gemma 4**, **Best Open-Source AI Project**.

## Tagline
UA: AI-підтримка, яка не відповідає, а вирішує: діє за правилами бізнесу і кличе людину лише коли правила цього вимагають.
EN: Support AI that doesn't just answer, it acts: within your business rules, and asks a human only when the rules say so.

## Пітч за хвилинами

**0:00-0:30 Проблема** (з `IDEA.md`)
- Чат-боти пояснюють, але не діють: дію все одно робить людина.
- При передачі людині губиться контекст: клієнт переказує все заново.
- Бізнеси бояться давати AI права: помилковий refund коштує грошей. Правила в бізнесів різні, жорстка автоматизація їх не покриває.

**0:30-0:50 Для кого**
Середні бізнеси за записом (салони, клініки, студії): великі мають власні системи, малим не треба, а відділу підтримки
в середніх немає, адміністратор тоне в повідомленнях і дзвінках.

**0:50-1:30 Що ми зробили**
- Платформа (тіммейт): мультитенант-бронювання, чат-віджет, адмінка, HTTP API і MCP-сервер, 2 бізнеси з різними правилами.
- Агент (ми): читає профіль клієнта і правила, діє tools (перенести, скасувати, повернути, goodwill), показує картки.
- Вживу: Олена (автоматично), Максим (апрув), Петро (сувора клініка). Один запит, три результати.

**1:30-2:15 Де тут AI**
- Оркестратор (Claude Sonnet 5.5 через LangChain) тріажить кожне повідомлення: намір, терміновість, емоція, регістр, маршрут.
- Gemma 4 відповідає на прості інформаційні питання (відкрита модель, Gemini API або локально через Ollama).
- Воркер (Claude Sonnet 5.5) міркує і викликає tools; між викликом і дією стоїть permission engine.
- Staged autonomy: кожен tool = `Allow | NeedsApproval | Forbidden` за дозволами тенанта; ризикове йде на approval card.
- Розуміє емоції та говірку/суржик ("блін, не встигаю"), відповідає літературною, сильний гнів передає людині.

**2:15-2:35 Архітектура (5 рядків)**
1. Клієнт: чат сайту (вебхук `/chat`) або copilot-UI; опційно телефон через Vapi.
2. FastAPI-сервіс агента: оркестратор (LangChain) -> Gemma 4 (прості) або воркер (дії).
3. Воркер викликає наші tools; кожен проходить permission engine (чиста функція, табличні тести).
4. Дані: протокол `DataSource` (пам'ять / HTTP платформи тіммейта), події й апруви в агента.
5. Copilot адміністратора читає потік подій: тріаж, виклики tools, approval cards, метрики. 186 тестів.

**2:35-2:50 Чим не чат-бот**
Діє (реальні зміни записів), пояснює кожне рішення причиною, зберігає контекст при апруві, права задає власник бізнесу, а не модель.

**2:50-3:00 Метрики власника і далі**
Метрики: сесії, автономні дії, апруви, ескалації, `money_saved_uah`, розподіл намірів і емоцій.
Далі: повна інтеграція з платформою через MCP, перевірений голос, тріаж і щоденне зведення, відкат дій.

## Критерій -> що сказати/показати

| Критерій | Що сказати | Що показати |
|---|---|---|
| Operational Impact | Менше ручної роботи: рутина вирішується без людини, людина лише на ризикових рішеннях | Сцена A без кліків адміна; метрики `money_saved_uah`, автономні дії |
| Innovation | Staged autonomy, яку налаштовує тенант; один агент, різні правила бізнесів | Сцена D: три результати на один запит; approval card |
| Use of AI | Дві ролі моделей: Sonnet оркеструє і діє, Gemma 4 відповідає на прості питання; емоції і говірка | Бейдж тріажу, tool-виклики, "блін, не встигаю" |
| Reasoning & Context | Політика тенанта x історія клієнта x емоція дають різні дії; рішення пояснене | Copilot: профіль (0 vs 2 неявки), причина Allow/NeedsApproval |
| Presentation & Demo | Два екрани, живий апрув, картки замість стіни тексту | Сцени A-C за `DEMO.md`, метрики в кінці |
| Best Use of Gemma 4 | Gemma 4 (відкриті ваги) відповідає на прості питання, працює локально через Ollama | Тріаж `route: answer` -> відповідь без воркера |
| Best Open-Source AI Project | Відкритий стек, репозиторій, тести, документація кожної фічі | GitHub, FastAPI, LangChain, `pytest` |

## Submission text (EN, <= 250 words)

**Support AI that doesn't just answer, it acts: within your business rules, and asks a human only when the rules say so.**

Most support chatbots explain but don't act, lose context on handoff, and businesses are afraid to give AI the power to refund or reschedule. We built a multi-tenant booking platform (salons, clinics) and a support agent that resolves requests instead of just replying.

For every customer message, an orchestrator (Claude Sonnet 5.5 via LangChain) triages intent, urgency, emotion and register, and understands colloquial Ukrainian, slang and dialect. Simple informational questions are answered by Gemma 4 (open weights, served through the Gemini API or locally through Ollama). Anything that changes data goes to a worker agent (Claude Sonnet 5.5) that calls tools: reschedule, cancel, refund, goodwill exception. Between the model and the action sits a permission engine: each tool call is Allow, NeedsApproval or Forbidden according to per-tenant permissions and customer history. Risky actions appear as an approval card in an administrator copilot with the full reasoning; after approval the agent continues the conversation itself. Customers see interactive cards (slots, decision summary).

The same request ("my child is ill, I can't come tomorrow") gives three different outcomes: automatic goodwill for a loyal customer, human approval for a customer with no-shows, and a strict approval-only flow at a clinic. Owners see metrics: autonomous actions, approvals, escalations, money saved.

Stack: FastAPI, LangChain, MCP server and Next.js/Postgres platform, Ollama, Gemma 4 open weights; 186 automated tests, fully documented, open source.

## Чого НЕ можна стверджувати
- Що Gemma 4 керує діями, міркує над рішеннями чи є основним агентом. Вона лише відповідає на прості питання; дії і тріаж роблять Claude Sonnet 5.5.
- Що весь продукт працює на Gemma 4 / "на відкритих моделях". Оркестратор і воркер є Claude Sonnet 5.5 (закрита модель).
- Що телефонія/голос працюють, доки не проведено живий дзвінок; казати "експериментальний канал" або мовчати.
- Що агент ходить у платформу через MCP: агент використовує `HttpDataSource` (`APP_API_URL`), `McpDataSource` немає; MCP-сервер є в платформі, але агент його не викликає.
- Що є тріаж-зведення дня, відкат дій, реальні SMS/платежі: їх немає (є лише ідея в `IDEA.md`).
- Цифри економії/CSAT на реальних бізнесах: метрики рахуються лише на демо-даних.
- Що журі бачить "живу" Gemma, якщо вона лише в fallback або вимкнена: перевірте `ANSWERER=on` до демо.
