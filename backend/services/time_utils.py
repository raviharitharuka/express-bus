import os
import re
from datetime import date, datetime, timedelta


def to_min(hhmm: str) -> int:
    """'09:15' -> 555. Raises ValueError unless it's a real time of day (H:MM or HH:MM)."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", hhmm.strip())
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        raise ValueError(f"'{hhmm}' is not a valid HH:MM time")
    return int(m[1]) * 60 + int(m[2])


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hours(minutes: float) -> float:
    return round(minutes / 60, 1)


def today() -> date:
    """Override with DEMO_DATE=YYYY-MM-DD to pin the demo to the calendar."""
    if demo := os.getenv("DEMO_DATE"):
        return date.fromisoformat(demo)
    return date.today()


def tomorrow() -> date:
    return today() + timedelta(days=1)


def now_hhmm() -> str:
    """Override with DEMO_TIME=HH:MM so the demo isn't run against an empty night schedule."""
    return os.getenv("DEMO_TIME") or datetime.now().strftime("%H:%M")
