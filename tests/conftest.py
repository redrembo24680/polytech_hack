from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from agent.datasource import MemoryDataSource

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
SEED_PATH = Path(__file__).resolve().parent.parent / "agent" / "seed.json"


@pytest.fixture
def ds():
    return MemoryDataSource.from_file(SEED_PATH, NOW)
