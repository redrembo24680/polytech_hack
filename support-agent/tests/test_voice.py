import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from agent.datasource import MemoryDataSource
from agent.main import create_app
from tests.conftest import NOW, SEED_PATH

OLENA, MAX = "+380501110001", "+380501110002"


def make():
    ds = MemoryDataSource.from_file(SEED_PATH, NOW)
    return TestClient(create_app(ds=ds, now_fn=lambda: NOW)), ds


def body(phone, name, args=None, tc_id="tc1", mtype="tool-calls"):
    return {"message": {"type": mtype, "call": {"customer": {"number": phone}},
                        "toolCallList": [{"id": tc_id, "type": "function",
                                          "function": {"name": name, "arguments": args or {}}}]}}


def test_profile_lookup():
    c, _ = make()
    r = c.post("/voice/tools", json=body(OLENA, "get_client_profile"))
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["toolCallId"] == "tc1" and '"visits_count": 12' in res["result"]


def test_unknown_phone():
    c, _ = make()
    r = c.post("/voice/tools", json=body("+380990000000", "get_client_profile"))
    assert r.status_code == 200 and "номер телефону" in r.json()["results"][0]["result"]


def test_unknown_caller_id_can_identify_by_spoken_phone():
    c, _ = make()
    r = c.post("/voice/tools", json=body("+380990000000", "identify_caller", {"phone": "0501110001"}))
    assert '"identified"' in r.json()["results"][0]["result"]


def test_identify_caller_cannot_rebind():
    c, _ = make()
    r = c.post("/voice/tools", json=body(OLENA, "identify_caller", {"phone": MAX}))
    assert "already_identified" in r.json()["results"][0]["result"]
    s = c.app.state.sessions["voice:lumen:+380501110001"]
    assert s.client_id == "olena"


def test_write_creates_pending_approval():
    c, _ = make()
    prof = c.post("/voice/tools", json=body(MAX, "get_client_profile")).json()["results"][0]["result"]
    import json
    bid = json.loads(prof)["bookings"][0]["id"]
    r = c.post("/voice/tools", json=body(MAX, "apply_goodwill_exception", {"booking_id": bid, "reason": "тест"}))
    assert r.status_code == 200
    assert len(c.get("/tenants/lumen/approvals?status=pending").json()["approvals"]) == 1


def test_non_tool_message():
    c, _ = make()
    assert c.post("/voice/tools", json={"message": {"type": "status-update"}}).json() == {"ok": True}


def test_session_reuse():
    c, _ = make()
    c.post("/voice/tools", json=body(OLENA, "get_client_profile"))
    n1 = len(c.get("/sessions/voice:lumen:+380501110001/events").json()["events"])
    c.post("/voice/tools", json=body("0501110001", "get_client_profile"))
    n2 = len(c.get("/sessions/voice:lumen:+380501110001/events").json()["events"])
    assert n1 > 0 and n2 > n1


def test_manual_endpoint_off_by_default():
    c, _ = make()
    assert c.post("/voice/tools/get_client_profile", json={"phone": OLENA}).status_code in (404, 405)


def test_manual_endpoint_and_show_card_sms(monkeypatch):
    monkeypatch.setenv("VOICE_MANUAL", "1")
    c, ds = make()
    card = {"type": "decision", "title": "Т", "outcome": "О", "reasoning": ["а"], "actions_taken": ["б"]}
    r = c.post("/voice/tools/show_card", json={"phone": OLENA, "args": {"card": card}})
    assert r.json()["result"] == "картку надіслано SMS"
    assert any(m.channel == "sms" and "О" in m.text for m in ds._messages)


def test_build_assistant_payload():
    spec = importlib.util.spec_from_file_location(
        "vapi_setup", Path(__file__).resolve().parent.parent / "scripts" / "vapi_setup.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    from agent.tools import default_registry
    decls = default_registry().declarations()
    p = m.build_assistant_payload(decls, "https://x.ngrok.app/")
    assert p["server"]["url"] == "https://x.ngrok.app/voice/tools"
    tools = p["model"]["tools"]
    assert len(tools) == len(decls) and tools[0]["function"]["name"] == decls[0]["name"]
    assert tools[0]["server"]["url"] == "https://x.ngrok.app/voice/tools"
    assert p["transcriber"]["language"] == "uk"
    assert p["voice"]["voiceId"].startswith("uk-UA") and p["serverMessages"] == ["tool-calls"]


def test_web_call_without_number_needs_identify():
    import json
    c, _ = make()

    def call(name, args=None):
        b = body("", name, args)
        b["message"]["call"] = {"id": "call-1", "customer": {}}
        return c.post("/voice/tools", json=b).json()["results"][0]["result"]

    assert "назвіть номер" in call("get_client_profile")
    assert "не знайдено" in call("identify_caller", {"phone": "0990000000"})
    assert "назвіть номер" in call("get_client_profile")
    ok = json.loads(call("identify_caller", {"phone": "050 111 00 01"}))
    assert ok["status"] == "identified"
    assert '"visits_count": 12' in call("get_client_profile")


def test_vapi_setup_includes_identify_caller():
    spec = importlib.util.spec_from_file_location(
        "vapi_setup2", Path(__file__).resolve().parent.parent / "scripts" / "vapi_setup.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    from agent.voice import voice_registry
    names = [d["name"] for d in voice_registry([]).declarations()]
    assert "identify_caller" in names
