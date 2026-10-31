import re


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0") and len(digits) == 10:
        return "38" + digits
    return digits
