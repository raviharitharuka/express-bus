import os
from datetime import date, datetime, timedelta


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


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
