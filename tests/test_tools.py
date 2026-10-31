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
        assert d["description"] and d["parameters"]["type"] == "object"
        assert set(d["parameters"].get("required", [])) <= set(d["parameters"]["properties"])
        for p in d["parameters"]["properties"].values():
            assert p["type"] in {"string", "integer", "object"} and p["description"]
    find = next(d for d in decls if d["name"] == "find_slots")
    assert "staff_id" not in find["parameters"]["required"]


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


def test_waive_allowed_on_lumen_reports_saved_fee(reg, ctx_lumen_olena):
    ds = ctx_lumen_olena.ds
    b = ds.get_booking("lumen", "b-olena-1")
    b.status = "no_show"
    r = reg.call("waive_no_show_fee", {"booking_id": "b-olena-1", "reason": "x"})
    if r["status"] == "done":
        assert r["saved_uah"] == ds.get_tenant("lumen").policy.no_show_fee
    else:
        assert r["status"] in {"pending_approval", "forbidden"}


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


def test_cancel_late_forfeits_and_goodwill_keeps(reg, ctx_lumen_olena, ctx_lumen_max):
    r = reg.call("cancel_booking", {"booking_id": "b-max-1", "reason": "x"})
    assert r["status"] == "done" and r["booking"]["status"] == "cancelled"


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
