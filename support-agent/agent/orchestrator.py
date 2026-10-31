"""Оркестратор на Claude Sonnet (LangChain): тріаж кожного повідомлення клієнта і вибір маршруту.

Оркестратор лише радить; на дуже прості питання відповідає Answerer (Gemma 4). Усі дії виконує воркер через tools/policy/approvals.
"""
import os
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.lingo import EMOTIONS, render_glossary

INTENTS = ("reschedule", "cancel", "refund", "question", "complaint", "other")
URGENCIES = ("low", "normal", "high", "urgent")
TONES = ("calm", "upset", "angry")
REGISTERS = ("formal", "casual", "slang")
ROUTES = ("agent", "answer", "escalate")
ACTION_INTENTS = frozenset({"reschedule", "cancel", "refund"})

SYSTEM_PROMPT = """Ти — оркестратор підтримки платформи онлайн-записів (салони, клініки). \
Для кожного повідомлення клієнта визнач намір, терміновість, емоцію і тон та обери маршрут. \
Клієнти пишуть розмовною українською: суржик, галицька говірка, чат-сленг, помилки. Розумій їх так:
{GLOSSARY}

Правила закладу:
{tenant_rules}

Клієнт: {client_summary}

Відповідай ЛИШЕ одним JSON-об'єктом, без жодного тексту до чи після нього і без markdown.

Поля відповіді (СТРОГИЙ JSON, без пояснень і markdown):
- intent: одне з reschedule, cancel, refund, question, complaint, other
- urgency: одне з low, normal, high, urgent
- tone: одне з calm, upset, angry
- route: agent (основний агент діє через інструменти), answer (проста інформаційна відповідь), \
escalate (передати людині)
- emotion: одне з calm, anxious, sad, frustrated, angry, happy
- intensity: ціле 1-3 (наскільки сильна емоція)
- register: formal, casual або slang (як пише клієнт)
- normalized: запит нейтральною літературною українською, до 20 слів
- hint: одне речення українською з порадою агенту, що перевірити

Зміни запису, скасування і повернення коштів завжди route = agent. \
answer — лише для простих питань без терміновості. escalate — лише для скарг у гніві або дуже термінових.

Приклади:
Клієнт: «блін, я не встигаю завтра, можна переставити?»
{{"intent":"reschedule","urgency":"normal","tone":"upset","emotion":"frustrated","intensity":2,\
"register":"casual","normalized":"Клієнт просить перенести запис на завтра","route":"agent","hint":"Перевір, чи зміна пізня."}}
Клієнт: «та ви шо, знову списали?!»
{{"intent":"refund","urgency":"high","tone":"angry","emotion":"angry","intensity":3,\
"register":"slang","normalized":"Клієнт обурений повторним списанням коштів","route":"agent","hint":"Перевір списання й передоплату."}}
Клієнт: «дякую, все файно, до зустрічі»
{{"intent":"other","urgency":"low","tone":"calm","emotion":"happy","intensity":1,\
"register":"casual","normalized":"Клієнт дякує і прощається","route":"agent","hint":""}}"""
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{GLOSSARY}", render_glossary().replace("{", "{{").replace("}", "}}"))

ANSWER_PROMPT_TEXT = ("Ти асистент підтримки закладу. Відповідай коротко і по суті лише на інформаційні питання, "
                      "спираючись на правила закладу. Не обіцяй дій.\n\nПравила закладу:\n{tenant_rules}\n\n"
                      "Клієнт: {client_summary}")
ANSWER_PROMPT = ChatPromptTemplate.from_messages([("system", ANSWER_PROMPT_TEXT), ("human", "{question}")])

PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{text}")])


@dataclass(frozen=True)
class Triage:
    intent: str
    urgency: str
    tone: str
    route: str
    hint: str
    model: str
    emotion: str = "calm"
    intensity: int = 1
    normalized: str = ""
    register: str = "formal"

    def payload(self) -> dict:
        data = {"intent": self.intent, "urgency": self.urgency, "tone": self.tone,
                "route": self.route, "hint": self.hint, "model": self.model,
                "emotion": self.emotion, "intensity": self.intensity,
                "normalized": self.normalized, "register": self.register}
        return data


def tone_from_emotion(emotion: str) -> str:
    if emotion == "angry":
        return "angry"
    return "upset" if emotion in ("frustrated", "anxious", "sad") else "calm"


def _enforce_route(intent: str, urgency: str, tone: str, route: str,
                   emotion: str = "calm", intensity: int = 1) -> str:
    if intent in ACTION_INTENTS:
        return "agent"
    if intent == "complaint" and emotion == "angry" and intensity >= 3:
        return "escalate"
    if route == "answer" and intent == "question" and urgency in ("low", "normal"):
        return "answer"
    if route == "escalate" and intent == "complaint" and (tone == "angry" or urgency == "urgent"):
        return "escalate"
    return "agent"


class Answerer:
    """Відповідає (Gemma 4) лише на дуже прості інформаційні питання."""

    def __init__(self, chat_model: BaseChatModel, model_name: str, timeout_s: float = 20.0):
        self.model_name, self.timeout_s = model_name, timeout_s
        self._chain = ANSWER_PROMPT | chat_model | StrOutputParser()

    def answer(self, question: str, tenant_rules: str, client_summary: str) -> str | None:
        try:
            out = self._chain.invoke({"question": question, "tenant_rules": tenant_rules,
                                      "client_summary": client_summary},
                                     config={"timeout": self.timeout_s})
            return str(out).strip() or None
        except Exception:
            return None


class Orchestrator:
    def __init__(self, chat_model: BaseChatModel, model_name: str, answerer: Answerer | None = None,
                 timeout_s: float = 20.0):
        self.model_name, self.timeout_s, self.answerer = model_name, timeout_s, answerer
        self._chain = PROMPT | chat_model | JsonOutputParser()

    def triage(self, text: str, tenant_rules: str, client_summary: str) -> Triage | None:
        try:
            data = self._chain.invoke({"text": text, "tenant_rules": tenant_rules,
                                       "client_summary": client_summary},
                                      config={"timeout": self.timeout_s})
            intent, urgency = data["intent"], data["urgency"]
            route = data["route"]
            emotion = data.get("emotion")
            tone = tone_from_emotion(emotion) if emotion in EMOTIONS else data["tone"]
            if intent not in INTENTS or urgency not in URGENCIES or tone not in TONES or route not in ROUTES:
                return None
            if emotion not in EMOTIONS:
                emotion = "calm"
            try:
                intensity = max(1, min(3, int(data.get("intensity") or 1)))
            except (TypeError, ValueError):
                intensity = 1
            register = data.get("register")
            if register not in REGISTERS:
                register = "formal"
            normalized = str(data.get("normalized") or "").strip()
            route = _enforce_route(intent, urgency, tone, route, emotion, intensity)
            hint = str(data.get("hint") or "").strip()
            return Triage(intent, urgency, tone, route, hint, self.model_name,
                          emotion, intensity, normalized, register)
        except Exception:
            return None


def _make_answerer() -> Answerer | None:
    if os.environ.get("ANSWERER", "on").lower() == "off":
        return None
    if os.environ.get("ANSWERER_PROVIDER", "ollama").lower() == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = os.environ.get("ANSWERER_MODEL", "gemma-4-31b-it")
        return Answerer(ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0), model)
    from langchain_ollama import ChatOllama

    model = os.environ.get("ANSWERER_MODEL", "gemma4:12b")
    base_url = os.environ.get("ANSWERER_BASE_URL", "http://localhost:11434")
    return Answerer(ChatOllama(model=model, base_url=base_url, temperature=0), model)


def make_orchestrator() -> Orchestrator | None:
    if os.environ.get("ORCHESTRATOR", "on").lower() == "off":
        return None
    provider = os.environ.get("ORCHESTRATOR_PROVIDER", "anthropic").lower()
    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = os.environ.get("ORCHESTRATOR_MODEL", "gemma-4-31b-it")
        chat = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model = os.environ.get("ORCHESTRATOR_MODEL", "gemma4:12b")
        base_url = os.environ.get("ORCHESTRATOR_BASE_URL", "http://localhost:11434")
        chat = ChatOllama(model=model, base_url=base_url, temperature=0, format="json")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        from langchain_anthropic import ChatAnthropic

        model = os.environ.get("ORCHESTRATOR_MODEL", "claude-sonnet-5-5")
        chat = ChatAnthropic(model=model, api_key=api_key, max_tokens=512)
    return Orchestrator(chat, model, _make_answerer())
