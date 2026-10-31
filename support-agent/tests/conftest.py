from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from agent.datasource import MemoryDataSource
from agent.policy import PolicyContext

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
SEED_PATH = Path(__file__).resolve().parent.parent / "agent" / "seed.json"


@pytest.fixture
def ds():
    return MemoryDataSource.from_file(SEED_PATH, NOW)



def _fresh_ds() -> MemoryDataSource:
    return MemoryDataSource.from_file(SEED_PATH, NOW)


def policy(tenant_id: str):
    return _fresh_ds().get_tenant(tenant_id).policy


def booking(tenant_id: str, booking_id: str):
    return _fresh_ds().get_booking(tenant_id, booking_id)


def ctx(tenant_id: str, client_id: str, booking_id: str | None, amount: int | None = None) -> PolicyContext:
    source = _fresh_ds()
    return PolicyContext(
        policy=source.get_tenant(tenant_id).policy,
        client=source.get_client(tenant_id, client_id),
        booking=source.get_booking(tenant_id, booking_id) if booking_id else None,
        now=NOW,
        amount=amount,
    )


def iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_ctx(tenant_id: str, client_id: str):
    from agent.context import SessionCtx, use
    from agent.events import ApprovalStore, EventLog

    session = SessionCtx(
        session_id="s1", tenant_id=tenant_id, client_id=client_id, now=NOW,
        ds=_fresh_ds(), events=EventLog(), approvals=ApprovalStore(),
    )
    with use(session):
        yield session


@pytest.fixture
def reg():
    from agent.tools import default_registry

    return default_registry()


@pytest.fixture
def ctx_lumen_olena():
    yield from _make_ctx("lumen", "olena")


@pytest.fixture
def ctx_lumen_max():
    yield from _make_ctx("lumen", "max")


@pytest.fixture
def ctx_denta_petro():
    yield from _make_ctx("denta", "petro")


@pytest.fixture
def ctx_denta_anna():
    yield from _make_ctx("denta", "anna")


@pytest.fixture
def sess_factory():
    from agent.agent import Session
    from agent.events import ApprovalStore, EventLog
    from agent.tools import default_registry

    def make(tenant_id: str, client_id: str, llm):
        return Session(
            id="s-test", tenant_id=tenant_id, client_id=client_id, channel="chat",
            ds=_fresh_ds(), events=EventLog(), approvals=ApprovalStore(),
            llm=llm, registry=default_registry(), now_fn=lambda: NOW,
        )

    return make


@pytest.fixture(autouse=True)
def _no_real_orchestrator(monkeypatch):
    """Tests never talk to a real Gemma: create_app's default make_orchestrator() must return None."""
    monkeypatch.setenv("ORCHESTRATOR", "off")


@pytest.fixture(autouse=True)
def _no_phone_verification(monkeypatch):
    """Existing tests run without SMS verification; OTP tests opt in with VERIFY_PHONE=1."""
    monkeypatch.setenv("VERIFY_PHONE", "0")
    monkeypatch.delenv("VERIFY_PHONE_DEMO_CODE", raising=False)
