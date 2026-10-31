import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from booking import clock
from booking.db import Base, get_session
from booking.main import create_app

NOW = datetime(2026, 11, 2, 8, 0, tzinfo=ZoneInfo("Europe/Kyiv"))  # Monday

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://booking:booking@localhost:5433/booking_test",
)

test_engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    test_engine.dispose()


@pytest.fixture(autouse=True)
def _clean_db(_schema):
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if names:
        with test_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {names} CASCADE"))
    yield


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)


@pytest.fixture
def session():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(session):
    app = create_app(init_db=False)

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
