from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Kyiv")


def now() -> datetime:
    """Current aware datetime in Europe/Kyiv. Tests monkeypatch this."""
    return datetime.now(TZ)
