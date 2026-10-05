"""Startup settings, read once from backend/.env. Real environment variables take precedence.

DATA_SOURCE  synthetic (default): data/{timetable,stations,drivers,buses,routes}.json, the demo dataset
             real: the same files with a _real suffix, built from VGN GTFS by scripts/build_real_timetable.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")  # also provides DEMO_DATE / DEMO_TIME if set there

DATA_SOURCES = ("synthetic", "real")
DATA_SOURCE = os.getenv("DATA_SOURCE", "synthetic").strip().lower()
if DATA_SOURCE not in DATA_SOURCES:
    raise RuntimeError(f"DATA_SOURCE must be 'synthetic' or 'real', got {DATA_SOURCE!r} (check backend/.env)")
