import pytest

from booking.phone import normalize_phone


@pytest.mark.parametrize("raw,expected", [
    ("+380 67 123-45-67", "380671234567"),
    ("0671234567", "380671234567"),
    ("380671234567", "380671234567"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected
