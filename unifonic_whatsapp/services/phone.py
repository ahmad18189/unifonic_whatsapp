import re

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str:
    """Only accept explicit E.164. Never guess locale or silently modify a phone number."""
    value = str(value or "").strip()
    if not PHONE_RE.fullmatch(value):
        raise ValueError("Phone must be in E.164 format, e.g. +9665XXXXXXXX")
    return value
