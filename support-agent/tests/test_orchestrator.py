import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.orchestrator import Orchestrator, make_orchestrator


def tri(**kw):
    base = {"intent": "question", "urgency": "low", "tone": "calm", "route": "agent",
            "hint": "Порада.", "reply": ""}
    return json.dumps({**base, **kw})


def run(response, text="привіт"):
    return Orchestrator(FakeListChatModel(responses=[response]), "gemma-test").triage(text, "правила", "клієнт")


def test_valid_json_becomes_triage():
    t = run(tri(intent="reschedule", urgency="high", tone="upset", hint="Перевір goodwill."))
    assert (t.intent, t.urgency, t.tone, t.route, t.hint, t.model) == (
        "reschedule", "high", "upset", "agent", "Перевір goodwill.", "gemma-test")
    assert t.reply is None


def test_refund_answer_is_coerced_to_agent():
    t = run(tri(intent="refund", route="answer", reply="Повернемо."))
    assert t.route == "agent" and t.reply is None


def test_question_low_answer_stays_answer():
    t = run(tri(route="answer", reply="Працюємо до 20:00."))
    assert t.route == "answer" and t.reply == "Працюємо до 20:00."


def test_question_high_urgency_answer_coerced():
    assert run(tri(urgency="high", route="answer", reply="x")).route == "agent"


def test_answer_without_reply_coerced():
    assert run(tri(route="answer")).route == "agent"


def test_complaint_angry_escalates():
    assert run(tri(intent="complaint", tone="angry", route="escalate")).route == "escalate"


def test_escalate_for_calm_question_coerced():
    assert run(tri(route="escalate")).route == "agent"


def test_invalid_json_returns_none():
    assert run("не json") is None


def test_missing_or_unknown_fields_return_none():
    assert run('{"intent":"question"}') is None
    assert run(tri(intent="weather")) is None


def test_model_exception_returns_none():
    class Boom(FakeListChatModel):
        def _call(self, *a, **k):
            raise RuntimeError("down")

    assert Orchestrator(Boom(responses=["x"]), "m").triage("a", "b", "c") is None


def test_make_orchestrator_off_and_no_network(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR", "off")
    assert make_orchestrator() is None
    monkeypatch.setenv("ORCHESTRATOR", "on")
    o = make_orchestrator()
    assert o is not None and o.model_name == "gemma4:12b"


def _chat_of(o):
    return o._chain.steps[1] if hasattr(o._chain, "steps") else o._chain.middle[0]


def test_default_provider_is_ollama(monkeypatch):
    from langchain_ollama import ChatOllama

    for k in ("ORCHESTRATOR_PROVIDER", "ORCHESTRATOR_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ORCHESTRATOR", "on")
    o = make_orchestrator()
    chat = _chat_of(o)
    assert isinstance(chat, ChatOllama) and chat.model == "gemma4:12b"


def test_gemini_provider_builds_google_model(monkeypatch):
    from langchain_google_genai import ChatGoogleGenerativeAI

    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.setenv("ORCHESTRATOR_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    o = make_orchestrator()
    assert o is not None and o.model_name == "gemma-4-31b-it"
    chat = _chat_of(o)
    assert isinstance(chat, ChatGoogleGenerativeAI) and chat.model.endswith("gemma-4-31b-it")


def test_gemini_provider_without_key_disabled(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.setenv("ORCHESTRATOR_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert make_orchestrator() is None
