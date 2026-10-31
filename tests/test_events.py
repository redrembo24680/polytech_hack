from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from agent.events import ApprovalStore, EventLog, metrics

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv"))


def test_emit_increments_ids_and_since_filters():
    log = EventLog(now_fn=lambda: T0)
    e1 = log.emit("s1", "t1", "user_message", {"text": "hi"})
    e2 = log.emit("s1", "t1", "assistant_message", {"text": "hello"})
    log.emit("s2", "t1", "user_message", {"text": "other"})
    assert (e1.id, e2.id) == (1, 2)
    assert e1.ts == T0
    assert [e.id for e in log.since("s1")] == [1, 2]
    assert [e.id for e in log.since("s1", after_id=1)] == [2]
    assert log.since("s1", after_id=2) == []


def test_approval_lifecycle():
    store = ApprovalStore(now_fn=lambda: T0)
    ap = store.create("s1", "t1", "refund_prepayment", {"booking_id": "b1"}, "over limit")
    assert ap.id == "ap-1"
    assert ap.status == "pending"
    assert ap.created_at == T0
    assert [a.id for a in store.pending("t1")] == ["ap-1"]
    assert store.pending("t2") == []
    done = store.decide("ap-1", True, "owner", "ok")
    assert done.status == "approved"
    assert done.decided_by == "owner"
    assert done.note == "ok"
    assert done.decided_at == T0
    assert store.get("ap-1").status == "approved"
    assert store.pending("t1") == []
    with pytest.raises(KeyError):
        store.get("ap-99")


def test_decide_twice_raises():
    store = ApprovalStore()
    store.create("s1", "t1", "cancel_booking", {}, "r")
    store.decide("ap-1", False, "owner", None)
    assert store.get("ap-1").status == "rejected"
    with pytest.raises(ValueError, match="already_decided"):
        store.decide("ap-1", True, "owner", None)


def test_metrics_counts():
    log = EventLog(now_fn=lambda: T0)
    store = ApprovalStore(now_fn=lambda: T0)
    log.emit("s1", "t1", "user_message", {})
    log.emit("s2", "t1", "user_message", {})
    log.emit("s1", "t1", "tool_call", {"name": "refund_prepayment", "decision": "allow"})
    log.emit("s1", "t1", "tool_call", {"name": "refund_prepayment", "decision": "allow"})
    log.emit("s1", "t1", "tool_call", {"name": "get_booking", "decision": "allow"})
    log.emit("s1", "t1", "tool_call", {"name": "escalate_to_human"})
    log.emit("s1", "t1", "tool_result", {"saved_uah": 500})
    log.emit("s1", "t1", "tool_result", {})
    log.emit("s9", "t2", "user_message", {})
    log.emit("s9", "t2", "tool_result", {"saved_uah": 1000})
    store.create("s1", "t1", "refund_prepayment", {}, "r")
    a2 = store.create("s1", "t1", "cancel_booking", {}, "r")
    a3 = store.create("s1", "t1", "cancel_booking", {}, "r")
    store.create("s9", "t2", "cancel_booking", {}, "r")
    store.decide(a2.id, True, "o", None)
    store.decide(a3.id, False, "o", None)
    assert metrics(log, store, "t1") == {
        "sessions": 2,
        "messages": 2,
        "tool_calls": 4,
        "auto_actions": 2,
        "approvals_pending": 1,
        "approvals_approved": 1,
        "approvals_rejected": 1,
        "escalations": 1,
        "money_saved_uah": 500,
    }


def test_emit_concurrent_ids_unique():
    log = EventLog(now_fn=lambda: T0)

    def work(i):
        return [log.emit(f"s{i}", "t1", "user_message", {}).id for _ in range(50)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = [x for chunk in pool.map(work, range(8)) for x in chunk]
    assert sorted(ids) == list(range(1, 401))
    assert len(log.for_tenant("t1")) == 400


def test_decide_concurrent_only_one_wins():
    store = ApprovalStore(now_fn=lambda: T0)
    store.create("s1", "t1", "refund_prepayment", {}, "r")

    def work(i):
        try:
            store.decide("ap-1", i % 2 == 0, f"u{i}", None)
            return "ok"
        except ValueError as e:
            return str(e)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(work, range(16)))
    assert results.count("ok") == 1
    assert results.count("already_decided") == 15


def test_metrics_reads_saved_uah_from_tool_result_payload():
    log = EventLog(now_fn=lambda: T0)
    log.emit("s1", "t1", "tool_result", {"name": "reschedule_booking", "result": {"status": "done", "saved_uah": 500}})
    log.emit("s1", "t1", "tool_result", {"name": "get_booking", "result": {"id": "b"}})
    assert metrics(log, ApprovalStore(now_fn=lambda: T0), "t1")["money_saved_uah"] == 500
