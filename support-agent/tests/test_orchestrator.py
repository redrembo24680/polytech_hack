import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.orchestrator import Orchestrator, make_orchestrator


def tri(**kw):
    base = {"intent": "question", "urgency": "low", "tone": "calm", "route": "agent",
            "hint": "Порада."}
    return json.dumps({**base, **kw})


def run(response, text="привіт"):
    return Orchestrator(FakeListChatModel(responses=[response]), "gemma-test").triage(text, "правила", "клієнт")


def test_valid_json_becomes_triage():
    t = run(tri(intent="reschedule", urgency="high", tone="upset", hint="Перевір goodwill."))
    assert (t.intent, t.urgency, t.tone, t.route, t.hint, t.model) == (
        "reschedule", "high", "upset", "agent", "Перевір goodwill.", "gemma-test")


def test_refund_answer_is_coerced_to_agent():
    assert run(tri(intent="refund", route="answer")).route == "agent"


def test_question_low_answer_stays_answer():
    assert run(tri(route="answer")).route == "answer"


def test_question_high_urgency_answer_coerced():
    assert run(tri(urgency="high", route="answer")).route == "agent"


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
    monkeypatch.setenv("ORCHESTRATOR_PROVIDER", "ollama")
    o = make_orchestrator()
    assert o is not None and o.model_name == "gemma4:12b"


def _chat_of(o):
    return o._chain.steps[1] if hasattr(o._chain, "steps") else o._chain.middle[0]


def test_default_provider_is_anthropic(monkeypatch):
    from langchain_anthropic import ChatAnthropic

    for k in ("ORCHESTRATOR_PROVIDER", "ORCHESTRATOR_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    o = make_orchestrator()
    assert o.model_name == "claude-sonnet-5-5"
    chat = _chat_of(o)
    assert isinstance(chat, ChatAnthropic) and chat.model == "claude-sonnet-5-5"


def test_default_provider_without_key_disabled(monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_PROVIDER", raising=False)
    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert make_orchestrator() is None


def test_answerer_defaults_to_gemma_ollama(monkeypatch):
    from langchain_ollama import ChatOllama

    for k in ("ANSWERER", "ANSWERER_PROVIDER", "ANSWERER_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    a = make_orchestrator().answerer
    assert a.model_name == "gemma4:12b" and isinstance(a._chain.steps[1], ChatOllama)


def test_answerer_off(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setenv("ANSWERER", "off")
    assert make_orchestrator().answerer is None


def test_answerer_returns_stripped_text():
    from agent.orchestrator import Answerer

    a = Answerer(FakeListChatModel(responses=["  Працюємо до 20:00.  "]), "g")
    assert a.answer("години?", "правила", "клієнт") == "Працюємо до 20:00."


def test_answerer_none_on_empty_or_exception():
    from agent.orchestrator import Answerer

    assert Answerer(FakeListChatModel(responses=["   "]), "g").answer("a", "b", "c") is None

    class Boom(FakeListChatModel):
        def _call(self, *a, **k):
            raise RuntimeError("down")

    assert Answerer(Boom(responses=["x"]), "g").answer("a", "b", "c") is None


def test_gemini_provider_builds_google_model(monkeypatch):
    from langchain_google_genai import ChatGoogleGenerativeAI

    monkeypatch.setenv("ORCHESTRATOR", "on")
    monkeypatch.setenv("ORCHESTRATOR_PROVIDER", "gemini")
    monkeypatch.setenv("ANSWERER", "off")
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


def test_new_fields_populated():
    t = run(tri(emotion="frustrated", intensity=2, normalized="Клієнт просить перенести запис", register="casual"))
    assert (t.emotion, t.intensity, t.normalized, t.register) == (
        "frustrated", 2, "Клієнт просить перенести запис", "casual")
    assert t.tone == "upset"
    p = t.payload()
    assert p["emotion"] == "frustrated" and p["intensity"] == 2 and p["register"] == "casual"
    assert p["normalized"].startswith("Клієнт")


def test_missing_new_fields_default():
    t = run(tri())
    assert (t.emotion, t.intensity, t.normalized, t.register) == ("calm", 1, "", "formal")


def test_bad_new_fields_default_not_none():
    t = run(tri(emotion="zzz", intensity="x", register="??", normalized=None))
    assert t is not None and (t.emotion, t.intensity, t.register) == ("calm", 1, "formal")
    assert run(tri(emotion="happy", intensity=9)).intensity == 3


def test_tone_derived_from_emotion():
    assert run(tri(emotion="angry")).tone == "angry"
    assert run(tri(emotion="sad", tone="calm")).tone == "upset"
    assert run(tri(emotion="happy", tone="angry")).tone == "calm"


def test_angry_3_complaint_escalates_even_if_model_said_agent():
    assert run(tri(intent="complaint", emotion="angry", intensity=3, route="agent")).route == "escalate"
    assert run(tri(intent="complaint", emotion="angry", intensity=2, tone="calm", route="agent")).route == "agent"


def test_prompt_contains_glossary_and_fewshot():
    from agent.orchestrator import PROMPT

    text = PROMPT.format_messages(text="x", tenant_rules="r", client_summary="c")[0].content
    assert "відмінити" in text and "скасувати" in text
    assert "та ви шо, знову списали" in text
    assert "emotion" in text and "normalized" in text
