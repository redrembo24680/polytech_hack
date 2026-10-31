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
    ap = s.approvals.decide(ap.id, True, "Оля", "ок")
    result = execute_approved(ap, s.ctx)
    assert s.resume_after_approval(ap, result) == "Адміністратор погодив, переношу."
    assert s.ds.get_client("lumen", "max").goodwill_exceptions[-1].booking_id == "b-max-1"
    assert "b-max-1" in s.ctx.goodwill_applied
    assert "[SYSTEM] Апрув" in fake.calls[2]["history"][-1].parts[0].text
    assert "approval_decided" in [e.type for e in s.events.since(s.id)]


def test_execute_approved_unknown_tool(sess_factory):
    s = sess_factory("lumen", "max", FakeClient([]))
    ap = s.approvals.create(s.id, "lumen", "nope", {}, "r")
    ap = s.approvals.decide(ap.id, True, "Оля", "ок")
    assert execute_approved(ap, s.ctx) == {"error": "unknown_tool"}


def _pending_goodwill(sess_factory):
    fake = FakeClient([Msg("model", [CallPart("apply_goodwill_exception", {"booking_id": "b-max-1", "reason": "x"})]),
                       Msg("model", [TextPart("Уточню.")])])
    s = sess_factory("lumen", "max", fake)
    s.send("x")
    return s, s.approvals.pending("lumen")[0]


def test_execute_approved_requires_approved_status(sess_factory):
    s, ap = _pending_goodwill(sess_factory)
    before = len(s.ds.get_client("lumen", "max").goodwill_exceptions)
    assert execute_approved(ap, s.ctx)["error"] == "not_approved"
    rejected = s.approvals.decide(ap.id, False, "Оля", "ні")
    assert execute_approved(rejected, s.ctx)["error"] == "not_approved"
    assert len(s.ds.get_client("lumen", "max").goodwill_exceptions) == before
    assert not s.ctx.goodwill_applied


def test_execute_approved_never_raises(sess_factory):
    s, ap = _pending_goodwill(sess_factory)
    ap = s.approvals.decide(ap.id, True, "Оля", "ок")
    bad = ap.model_copy(update={"args": {"booking_id": "b-max-1"}})
    assert execute_approved(bad, s.ctx)["error"] == "internal"


def _approved(s, tool, args):
    ap = s.approvals.create(s.id, s.tenant_id, tool, args, "r")
    return s.approvals.decide(ap.id, True, "Оля", None)


def test_scenario_c_refund_then_cancel_keeps_refunded(sess_factory):
    s = sess_factory("denta", "petro", FakeClient([]))
    r1 = execute_approved(_approved(s, "refund_prepayment", {"booking_id": "b-petro-1", "amount": 800, "reason": "x"}), s.ctx)
    r2 = execute_approved(_approved(s, "cancel_booking", {"booking_id": "b-petro-1", "reason": "x"}), s.ctx)
    assert r1["status"] == "done" and r2["status"] == "done"
    b = s.ds.get_booking("denta", "b-petro-1")
    assert b.status == "cancelled" and b.prepayment.status == "refunded"


def test_execute_approved_naive_start_uses_tenant_timezone(sess_factory):
    from datetime import timedelta

    late = NOW + timedelta(days=2, hours=2)
    s = sess_factory("lumen", "olena", FakeClient([]))
    args = {"booking_id": "b-olena-1", "start": late.replace(tzinfo=None).isoformat(), "reason": "x"}
    assert execute_approved(_approved(s, "reschedule_booking", args), s.ctx)["status"] == "done"
    assert s.ds.get_booking("lumen", "b-olena-1").start == late


def test_execute_approved_reads_goodwill_from_data(sess_factory):
    s = sess_factory("lumen", "max", FakeClient([]))
    s.ds.add_goodwill("lumen", "max", "b-max-1", "x", "human:Оля")  # e.g. approved in another session
    execute_approved(_approved(s, "cancel_booking", {"booking_id": "b-max-1", "reason": "x"}), s.ctx)
    assert s.ds.get_booking("lumen", "b-max-1").prepayment.status == "held"


def test_execute_approved_goodwill_twice_is_noop(sess_factory):
    s = sess_factory("lumen", "max", FakeClient([]))
    args = {"booking_id": "b-max-1", "reason": "x"}
    assert execute_approved(_approved(s, "apply_goodwill_exception", args), s.ctx)["status"] == "done"
    r = execute_approved(_approved(s, "apply_goodwill_exception", args), s.ctx)
    assert r["status"] == "done" and r["already_applied"] is True
    assert len(s.ds.get_client("lumen", "max").goodwill_exceptions) == 1


def test_execute_approved_holds_write_lock(sess_factory, monkeypatch):
    from agent.tools import WRITE_LOCK
    from tests.test_tools import _other_thread_can_acquire

    s = sess_factory("denta", "petro", FakeClient([]))
    seen = {}
    real = s.ds.cancel

    def spy(*a, **kw):
        seen["locked"] = not _other_thread_can_acquire(WRITE_LOCK)
        return real(*a, **kw)

    monkeypatch.setattr(s.ds, "cancel", spy)
    execute_approved(_approved(s, "cancel_booking", {"booking_id": "b-petro-1", "reason": "x"}), s.ctx)
    assert seen["locked"] is True
