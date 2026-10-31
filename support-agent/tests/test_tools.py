from datetime import timedelta

import pytest

from agent.context import SessionCtx, get_ctx
from tests.conftest import NOW, iso

LATE = NOW + timedelta(days=2, hours=2)


def test_registry_has_10_tools_with_schemas(reg):
    decls = reg.declarations()
    assert {d["name"] for d in decls} == {
        "get_client_profile", "get_booking", "find_slots", "reschedule_booking", "cancel_booking",
        "refund_prepayment", "apply_goodwill_exception", "waive_no_show_fee", "escalate_to_human", "show_card",
    }
    for d in decls:
        assert d["description"]
        if "parameters" not in d:
            continue
        assert d["parameters"]["type"] == "object" and d["parameters"]["properties"]
        assert set(d["parameters"].get("required", [])) <= set(d["parameters"]["properties"])
        for p in d["parameters"]["properties"].values():
            assert p["type"] in {"string", "integer", "object"} and p["description"]
    find = next(d for d in decls if d["name"] == "find_slots")
    assert "staff_id" not in find["parameters"]["required"]


def test_declarations_are_valid_gemini_function_declarations(reg):
    from google.genai import types

    decls = reg.declarations()
    assert "parameters" not in next(d for d in decls if d["name"] == "get_client_profile")
    card = next(d for d in decls if d["name"] == "show_card")["parameters"]["properties"]["card"]
    assert card["properties"] and card["description"]
    for d in decls:
        assert "parameters" not in d or d["parameters"]["properties"]
        fd = types.FunctionDeclaration(**d)
        assert fd.name == d["name"]


def test_booking_id_description_is_neutral(reg):
    for d in reg.declarations():
        for p in d.get("parameters", {}).get("properties", {}).values():
            assert "b-olena-1" not in p["description"]


def test_get_client_profile_returns_history(reg, ctx_lumen_olena):
    r = reg.call("get_client_profile", {})
    assert r["visits_count"] == 12 and r["bookings"][0]["id"] == "b-olena-1"


def test_goodwill_allowed_then_late_reschedule_keeps_prepayment(reg, ctx_lumen_olena):
    assert reg.call("apply_goodwill_exception", {"booking_id": "b-olena-1", "reason": "хвороба"})["status"] == "done"
    r = reg.call("reschedule_booking", {"booking_id": "b-olena-1", "start": iso(LATE), "reason": "хвороба"})
    assert r["status"] == "done" and r["booking"]["prepayment"]["status"] == "held" and r["saved_uah"] == 500


def test_late_reschedule_without_goodwill_forfeits(reg, ctx_lumen_max):
    r = reg.call("reschedule_booking", {"booking_id": "b-max-1", "start": iso(LATE), "reason": "x"})
    assert r["booking"]["prepayment"]["status"] == "forfeited"
    assert "saved_uah" not in r


def test_goodwill_for_max_creates_approval_and_does_not_apply(reg, ctx_lumen_max):
    r = reg.call("apply_goodwill_exception", {"booking_id": "b-max-1", "reason": "x"})
    assert r["status"] == "pending_approval" and r["instruction"]
    assert ctx_lumen_max.approvals.pending("lumen")[0].tool == "apply_goodwill_exception"
    assert ctx_lumen_max.ds.get_client("lumen", "max").goodwill_exceptions == []
    assert "b-max-1" not in ctx_lumen_max.goodwill_applied
    types = [e.type for e in ctx_lumen_max.events.since("s1")]
    assert types == ["tool_call", "approval_created", "tool_result"]
    assert ctx_lumen_max.events.since("s1")[0].payload["decision"] == "needs_approval"


def test_forbidden_waive_on_denta(reg, ctx_denta_anna):
    assert reg.call("waive_no_show_fee", {"booking_id": "b-anna-1", "reason": "x"})["status"] == "forbidden"
    assert ctx_denta_anna.events.since("s1")[0].payload["decision"] == "forbidden"


def test_waive_on_lumen_needs_approval(reg, ctx_lumen_olena):
    ds = ctx_lumen_olena.ds
    ds.get_booking("lumen", "b-olena-1").status = "no_show"
    r = reg.call("waive_no_show_fee", {"booking_id": "b-olena-1", "reason": "x"})
    assert r["status"] == "pending_approval" and "saved_uah" not in r
    assert ctx_lumen_olena.approvals.pending("lumen")[0].tool == "waive_no_show_fee"
    assert ds.get_booking("lumen", "b-olena-1").history == []


def test_data_error_surfaces_as_error(reg, ctx_lumen_olena):
    assert reg.call("refund_prepayment", {"booking_id": "b-olena-1", "amount": 900, "reason": "x"})["error"] == "validation"


def test_unknown_tool_and_bad_args(reg, ctx_lumen_olena):
    assert reg.call("nope", {})["error"] == "unknown_tool"
    assert reg.call("get_booking", {"wrong": 1})["error"] == "validation"
    assert reg.call("get_booking", {})["error"] == "validation"


def test_bad_iso_date_is_validation(reg, ctx_lumen_olena):
    r = reg.call("find_slots", {"service_id": "svc-cut", "from_date": "не дата", "to_date": "2026-11-05"})
    assert r["error"] == "validation"


def test_not_found_error_code(reg, ctx_lumen_olena):
    assert reg.call("get_booking", {"booking_id": "zzz"})["error"] == "not_found"


def test_find_slots_returns_slots(reg, ctx_lumen_olena):
    r = reg.call("find_slots", {"service_id": "svc-cut", "from_date": "2026-11-02", "to_date": "2026-11-03"})
    assert r["slots"] and "start" in r["slots"][0]


def test_late_cancel_without_goodwill_forfeits(reg, ctx_lumen_max):
    r = reg.call("cancel_booking", {"booking_id": "b-max-1", "reason": "x"})
    assert r["status"] == "done" and r["booking"]["status"] == "cancelled"
    assert r["booking"]["prepayment"]["status"] == "forfeited" and "saved_uah" not in r


def test_late_cancel_after_goodwill_keeps_prepayment(reg, ctx_lumen_olena):
    assert reg.call("apply_goodwill_exception", {"booking_id": "b-olena-1", "reason": "хвороба"})["status"] == "done"
    r = reg.call("cancel_booking", {"booking_id": "b-olena-1", "reason": "x"})
    assert r["booking"]["status"] == "cancelled" and r["booking"]["prepayment"]["status"] == "held"
    assert r["saved_uah"] == 500


def test_escalate_creates_ticket(reg, ctx_denta_petro):
    r = reg.call("escalate_to_human", {"summary": "скарга", "priority": "high"})
    assert r["status"] == "done" and r["ticket"]["priority"] == "high"


def test_show_card_emits_event(reg, ctx_lumen_olena):
    r = reg.call("show_card", {"card": {"type": "slots", "title": "t", "options": []}})
    assert r == {"status": "shown"}
    assert ctx_lumen_olena.events.since("s1")[-1].type == "card"


def test_tool_call_events_emitted(reg, ctx_lumen_olena):
    reg.call("get_booking", {"booking_id": "b-olena-1"})
    events = ctx_lumen_olena.events.since("s1")
    assert [e.type for e in events][-2:] == ["tool_call", "tool_result"]
    assert events[-2].payload["decision"] == "read"


def test_cross_tenant_booking_not_found(reg, ctx_denta_petro):
    assert reg.call("get_booking", {"booking_id": "b-olena-1"})["error"] == "not_found"


def test_get_ctx_without_session_raises():
    with pytest.raises(RuntimeError, match="no active session context"):
        get_ctx()


def test_ctx_is_dataclass_with_goodwill_default(ctx_lumen_olena):
    assert isinstance(ctx_lumen_olena, SessionCtx) and ctx_lumen_olena.goodwill_applied == set()


def test_cross_client_booking_is_not_found(reg, ctx_lumen_olena):
    assert reg.call("get_booking", {"booking_id": "b-max-1"})["error"] == "not_found"
    assert reg.call("cancel_booking", {"booking_id": "b-max-1", "reason": "x"})["error"] == "not_found"
    assert ctx_lumen_olena.ds.get_booking("lumen", "b-max-1").status == "scheduled"


def test_args_validated_per_tool(reg, ctx_lumen_olena):
    r = reg.call("cancel_booking", {"booking_id": "b-olena-1", "reason": "x", "start": iso(LATE)})
    assert r["error"] == "validation"
    r = reg.call("refund_prepayment", {"booking_id": "b-olena-1", "amount": "abc", "reason": "x"})
    assert r["error"] == "validation" and ctx_lumen_olena.approvals.pending("lumen") == []
    r = reg.call("refund_prepayment", {"booking_id": "b-olena-1", "amount": True, "reason": "x"})
    assert r["error"] == "validation"
    r = reg.call("reschedule_booking", {"booking_id": "b-olena-1", "start": "garbage", "reason": "x"})
    assert r["error"] == "validation"


def test_unexpected_exception_becomes_internal(reg, ctx_lumen_olena):
    from agent.tools import ToolSpec

    def boom() -> dict:
        raise RuntimeError("kaboom")

    reg.register(ToolSpec("boom", "t", {"type": "object", "properties": {}, "required": []}, boom))
    r = reg.call("boom", {})
    assert r["error"] == "internal"
    last = ctx_lumen_olena.events.since("s1")[-1]
    assert last.type == "tool_result" and "kaboom" in last.payload["detail"]


def test_policy_misconfiguration_is_internal(reg, ctx_lumen_olena):
    tenant = ctx_lumen_olena.ds.get_tenant("lumen")
    perms = tenant.policy.agent_permissions.model_copy(update={"cancel": "bogus"})
    tenant.policy.agent_permissions = perms
    assert reg.call("cancel_booking", {"booking_id": "b-olena-1", "reason": "x"})["error"] == "internal"


def test_show_card_rejects_invalid_card_without_event(reg, ctx_lumen_olena):
    r = reg.call("show_card", {"card": {"type": "slots", "title": "t", "options": [{"id": "1"}]}})
    assert r["error"] == "validation" and "options.0" in r["message"]
    assert "card" not in [e.type for e in ctx_lumen_olena.events.since("s1")]


def test_show_card_emits_validated_dump(reg, ctx_lumen_olena):
    card = {"type": "decision", "title": "t", "outcome": "o", "reasoning": ["r"], "actions_taken": [], "x": 1}
    assert reg.call("show_card", {"card": card}) == {"status": "shown"}
    ev = ctx_lumen_olena.events.since("s1")[-1]
    assert ev.type == "card" and ev.payload == {k: v for k, v in card.items() if k != "x"}


def test_naive_start_gets_tenant_timezone(reg, ctx_lumen_olena):
    naive = LATE.replace(tzinfo=None).isoformat()
    r = reg.call("reschedule_booking", {"booking_id": "b-olena-1", "start": naive, "reason": "x"})
    assert r["status"] == "done"
    assert ctx_lumen_olena.ds.get_booking("lumen", "b-olena-1").start == LATE


def test_null_optional_args_are_dropped(reg, ctx_lumen_olena):
    r = reg.call("find_slots", {"service_id": "svc-cut", "from_date": "2026-11-02", "to_date": "2026-11-02",
                                "staff_id": None})
    assert r["slots"]
    r = reg.call("reschedule_booking", {"booking_id": "b-olena-1", "start": iso(LATE), "reason": "x", "staff_id": None})
    assert r["status"] == "done"
    assert reg.call("get_booking", {"booking_id": None})["error"] == "validation"


def test_refund_on_scheduled_booking_needs_approval(reg, ctx_lumen_olena):
    r = reg.call("refund_prepayment", {"booking_id": "b-olena-1", "amount": 500, "reason": "x"})
    assert r["status"] == "pending_approval"
    assert ctx_lumen_olena.ds.get_booking("lumen", "b-olena-1").prepayment.status == "held"


def test_goodwill_is_read_from_data_in_a_new_session(reg, ctx_lumen_olena):
    from agent.context import SessionCtx, use

    assert reg.call("apply_goodwill_exception", {"booking_id": "b-olena-1", "reason": "хвороба"})["status"] == "done"
    c = ctx_lumen_olena
    fresh = SessionCtx("s2", c.tenant_id, c.client_id, c.now, c.ds, c.events, c.approvals)
    with use(fresh):
        r = reg.call("reschedule_booking", {"booking_id": "b-olena-1", "start": iso(LATE), "reason": "x"})
    assert r["booking"]["prepayment"]["status"] == "held" and r["saved_uah"] == 500


def test_second_goodwill_is_already_applied_noop(reg, ctx_lumen_olena):
    reg.call("apply_goodwill_exception", {"booking_id": "b-olena-1", "reason": "x"})
    r = reg.call("apply_goodwill_exception", {"booking_id": "b-olena-1", "reason": "x"})
    assert r["status"] == "done" and r["already_applied"] is True
    assert len(ctx_lumen_olena.ds.get_client("lumen", "olena").goodwill_exceptions) == 1
    assert ctx_lumen_olena.events.since("s1")[-2].payload["decision"] == "noop"


def test_goodwill_after_human_approval_is_noop(reg, ctx_lumen_max):
    ctx_lumen_max.ds.add_goodwill("lumen", "max", "b-max-1", "x", "human:Оля")
    r = reg.call("apply_goodwill_exception", {"booking_id": "b-max-1", "reason": "x"})
    assert r["already_applied"] is True and ctx_lumen_max.approvals.pending("lumen") == []


def _other_thread_can_acquire(lock) -> bool:
    import threading

    out = {}

    def probe():
        out["ok"] = lock.acquire(blocking=False)
        if out["ok"]:
            lock.release()

    t = threading.Thread(target=probe)
    t.start()
    t.join()
    return out["ok"]


def test_write_tool_runs_under_write_lock(reg, ctx_lumen_olena):
    from agent.tools import WRITE_LOCK

    seen = {}
    spec = reg.get("cancel_booking")
    real = spec.fn

    def spy(**kw):
        seen["locked"] = not _other_thread_can_acquire(WRITE_LOCK)
        return real(**kw)

    spec.fn = spy
    assert reg.call("cancel_booking", {"booking_id": "b-olena-1", "reason": "x"})["status"] == "done"
    assert seen["locked"] is True and _other_thread_can_acquire(WRITE_LOCK)
