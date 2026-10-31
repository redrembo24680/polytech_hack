from agent.agent import build_system_prompt, execute_approved
from agent.llm import CallPart, FakeClient, Msg, TextPart
from tests.conftest import NOW


def test_system_prompt_contains_rules_and_client(ds):
    p = build_system_prompt(ds.get_tenant("lumen"), ds.get_client("lumen", "olena"), NOW)
    assert "24 годин" in p and "Олена" in p and "12" in p and "show_card" in p


def test_loop_executes_tool_and_returns_text(sess_factory):
    fake = FakeClient([Msg("model", [TextPart("Перевіряю бронювання."), CallPart("get_booking", {"booking_id": "b-olena-1"})]),
                       Msg("model", [TextPart("Ваш запис завтра о 10:00.")])])
    s = sess_factory("lumen", "olena", fake)
    assert s.send("коли мій запис?") == "Ваш запис завтра о 10:00."
    types = [e.type for e in s.events.since(s.id)]
    assert types == ["user_message", "thinking", "tool_call", "tool_result", "assistant_message"]
    assert fake.calls[1]["history"][-1].role == "tool"


def test_loop_stops_at_max_iter_with_error_event(sess_factory):
    fake = FakeClient([Msg("model", [CallPart("get_booking", {"booking_id": "b-olena-1"})])] * 9)
    s = sess_factory("lumen", "olena", fake)
    s.send("x")
    assert s.events.since(s.id)[-1].type == "error"


def test_unknown_tool_does_not_crash(sess_factory):
    fake = FakeClient([Msg("model", [CallPart("nope", {})]), Msg("model", [TextPart("ok")])])
    assert sess_factory("lumen", "olena", fake).send("x") == "ok"


def test_llm_exception_is_caught(sess_factory):
    class Boom:
        def generate(self, system, history, tools):
            raise RuntimeError("network down")

    s = sess_factory("lumen", "olena", Boom())
    assert "технічна помилка" in s.send("x")
    last = s.events.since(s.id)[-1]
    assert last.type == "error" and last.payload["message"] == "network down"


def test_resume_after_approval_executes_and_continues(sess_factory):
    fake = FakeClient([Msg("model", [CallPart("apply_goodwill_exception", {"booking_id": "b-max-1", "reason": "x"})]),
                       Msg("model", [TextPart("Уточню в адміністратора.")]),
                       Msg("model", [TextPart("Адміністратор погодив, переношу.")])])
    s = sess_factory("lumen", "max", fake)
    s.send("дитина захворіла")
    ap = s.approvals.pending("lumen")[0]
    result = execute_approved(ap, s.ctx)
    ap = s.approvals.decide(ap.id, True, "Оля", "ок")
    assert s.resume_after_approval(ap, result) == "Адміністратор погодив, переношу."
    assert s.ds.get_client("lumen", "max").goodwill_exceptions[-1].booking_id == "b-max-1"
    assert "b-max-1" in s.ctx.goodwill_applied
    assert "[SYSTEM] Апрув" in fake.calls[2]["history"][-1].parts[0].text
    assert "approval_decided" in [e.type for e in s.events.since(s.id)]


def test_execute_approved_unknown_tool(sess_factory):
    s = sess_factory("lumen", "max", FakeClient([]))
    ap = s.approvals.create(s.id, "lumen", "nope", {}, "r")
    assert execute_approved(ap, s.ctx) == {"error": "unknown_tool"}
