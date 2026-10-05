"""Startup settings, read once from backend/.env. Real environment variables take precedence.

DATA_SOURCE  synthetic (default): the hand-made demo dataset, data/{timetable,stations,drivers,buses,routes}.json.
             gtfs: VAG Nürnberg city bus trips from the VGN GTFS feed, built by scripts/build_real_timetable.py.
                   Only trips, routes and stop names are real; duties, drivers, buses, express candidates
                   and distances are synthetic (GTFS has no rosters). See services/data.py:DATA_FILES.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")  # also provides DEMO_DATE / DEMO_TIME if set there

DATA_SOURCES = ("synthetic", "gtfs")
DATA_SOURCE = os.getenv("DATA_SOURCE", "synthetic").strip().lower()
if DATA_SOURCE == "real":
    raise RuntimeError("DATA_SOURCE=real was renamed to DATA_SOURCE=gtfs: only the trips are real, the drivers, "
                       "buses and duties are synthetic. Update backend/.env")
if DATA_SOURCE not in DATA_SOURCES:
    raise RuntimeError(f"DATA_SOURCE must be 'synthetic' or 'gtfs', got {DATA_SOURCE!r} (check backend/.env)")

DATA_NOTES = {
    "synthetic": "Hand-made demo dataset: all stations, trips, drivers and buses are invented.",
    "gtfs": "Trips, routes and stop names are real VGN GTFS data (VAG city buses, one weekday). "
            "Duties, drivers, buses, express candidates and distances are synthetic.",
}
DATA_NOTE = DATA_NOTES[DATA_SOURCE]
