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
