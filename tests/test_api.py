from fastapi.testclient import TestClient

from agent.llm import CallPart, FakeClient, Msg, TextPart
from agent.main import create_app
from tests.conftest import NOW, SEED_PATH
from agent.datasource import MemoryDataSource


def make(script, ds=None):
    ds = ds or MemoryDataSource.from_file(SEED_PATH, NOW)
    return TestClient(create_app(ds=ds, llm=FakeClient(script), now_fn=lambda: NOW)), ds


def new_session(c, tenant="lumen", client="max"):
    r = c.post("/sessions", json={"tenant_id": tenant, "client_id": client, "channel": "chat"})
    assert r.status_code == 200
    return r.json()["session_id"]


def test_create_session_and_message_flow():
    c, _ = make([Msg("model", [TextPart("Вітаю!")])])
    sid = new_session(c)
    assert sid == "s-1"
    r = c.post(f"/sessions/{sid}/messages", json={"text": "привіт"})
    assert r.status_code == 200 and r.json() == {"reply": "Вітаю!"}
    events = c.get(f"/sessions/{sid}/events").json()["events"]
    types = [e["type"] for e in events]
    assert "user_message" in types and "assistant_message" in types
    after = c.get(f"/sessions/{sid}/events", params={"after": events[-1]["id"]}).json()["events"]
    assert after == []


def test_unknown_client_404():
    c, _ = make([])
    r = c.post("/sessions", json={"tenant_id": "lumen", "client_id": "nope", "channel": "chat"})
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    r = c.post("/sessions", json={"tenant_id": "nope", "client_id": "max", "channel": "chat"})
    assert r.status_code == 404


def test_unknown_session_404():
    c, _ = make([])
    assert c.post("/sessions/s-9/messages", json={"text": "x"}).status_code == 404
    assert c.get("/sessions/s-9/events").status_code == 404


def test_busy_session_409():
    c, _ = make([])
    sid = new_session(c)
    lock = c.app.state.locks[sid]
    lock.acquire()
    try:
        r = c.post(f"/sessions/{sid}/messages", json={"text": "x"})
    finally:
        lock.release()
    assert r.status_code == 409 and r.json()["error"] == "busy"


def _pending(script_extra=()):
    script = [Msg("model", [CallPart("apply_goodwill_exception", {"booking_id": "b-max-1", "reason": "x"})]),
              Msg("model", [TextPart("Уточню в адміністратора.")]), *script_extra]
    c, ds = make(script)
    sid = new_session(c)
    assert c.post(f"/sessions/{sid}/messages", json={"text": "дитина захворіла"}).status_code == 200
    pending = c.get("/tenants/lumen/approvals", params={"status": "pending"}).json()["approvals"]
    assert len(pending) == 1
    return c, ds, pending[0]


def test_approval_decide_flow():
    c, ds, ap = _pending([Msg("model", [TextPart("Адміністратор погодив.")])])
    r = c.post(f"/approvals/{ap['id']}/decide", json={"approve": True, "note": "ок", "by": "Оля"})
    assert r.status_code == 200
    body = r.json()
    assert body["approval"]["status"] == "approved" and body["reply"] == "Адміністратор погодив."
    assert body["result"]["status"] == "done"
    assert c.get("/tenants/lumen/approvals").json()["approvals"] == []
    assert c.get("/tenants/lumen/metrics").json()["approvals_approved"] == 1
    assert ds.get_client("lumen", "max").goodwill_exceptions[-1].booking_id == "b-max-1"


def test_decide_reject_and_twice_409():
    c, ds, ap = _pending([Msg("model", [TextPart("Відхилено.")])])
    n = len(ds.get_client("lumen", "max").goodwill_exceptions)
    r = c.post(f"/approvals/{ap['id']}/decide", json={"approve": False, "note": None, "by": "Оля"})
    assert r.status_code == 200 and r.json()["result"] == {"status": "rejected"}
    assert len(ds.get_client("lumen", "max").goodwill_exceptions) == n
    r = c.post(f"/approvals/{ap['id']}/decide", json={"approve": True, "note": None, "by": "Оля"})
    assert r.status_code == 409 and r.json()["error"] == "already_decided"


def test_decide_unknown_404():
    c, _ = make([])
    r = c.post("/approvals/ap-99/decide", json={"approve": True, "note": None, "by": "x"})
    assert r.status_code == 404


def test_approvals_bad_status_400():
    c, _ = make([])
    assert c.get("/tenants/lumen/approvals", params={"status": "all"}).status_code == 400


def test_metrics_shape():
    c, _ = make([])
    m = c.get("/tenants/lumen/metrics").json()
    assert set(m) == {"sessions", "messages", "tool_calls", "auto_actions", "approvals_pending",
                      "approvals_approved", "approvals_rejected", "escalations", "money_saved_uah"}


def test_tenant_endpoint_lists_clients():
    c, _ = make([])
    body = c.get("/tenants/lumen").json()
    assert body["tenant"]["id"] == "lumen"
    assert "max" in {x["id"] for x in body["clients"]}
    assert c.get("/tenants/nope").status_code == 404


def test_execute_runs_under_session_lock(monkeypatch):
    import agent.main as m

    c, _, ap = _pending([Msg("model", [TextPart("ok")])])
    seen = {}
    real = m.execute_approved

    def spy(approval, ctx):
        seen["locked"] = c.app.state.locks[approval.session_id].locked()
        return real(approval, ctx)

    monkeypatch.setattr(m, "execute_approved", spy)
    r = c.post(f"/approvals/{ap['id']}/decide", json={"approve": True, "note": None, "by": "Оля"})
    assert r.status_code == 200 and seen["locked"] is True
    assert r.json()["result"]["status"] == "done" and r.json()["reply"] == "ok"


def test_framework_errors_are_flat():
    c, _ = make([])
    sid = new_session(c)
    r = c.get(f"/sessions/{sid}/events", params={"after": "abc"})
    assert r.status_code == 422 and r.json()["error"] == "validation"
    r = c.get("/nope")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    r = c.delete("/sessions")
    assert r.status_code == 405 and r.json()["error"] == "method_not_allowed"


def test_resume_failure_returns_result(monkeypatch):
    from agent.agent import Session

    c, _, ap = _pending()

    def boom(self, approval, result):
        raise RuntimeError("kaput")

    monkeypatch.setattr(Session, "resume_after_approval", boom)
    r = c.post(f"/approvals/{ap['id']}/decide", json={"approve": True, "note": None, "by": "Оля"})
    body = r.json()
    assert r.status_code == 200 and body["reply"] is None
    assert body["result"]["status"] == "done" and body["approval"]["status"] == "approved"
    assert body["error"]["error"] == "resume_failed"
    evs = c.get("/sessions/s-1/events").json()["events"]
    assert evs[-1]["type"] == "error" and evs[-1]["payload"]["message"] == "kaput"
