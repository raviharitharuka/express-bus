"""Convert the filtered VGN GTFS data into the demo's timetable/stations JSON shape.

Run from backend/ after scripts/filter_gtfs.py:
    python scripts/build_real_timetable.py

Reads data/filtered/*.csv and meta.json (repo root) and writes backend/data/timetable_real.json
and backend/data/stations_real.json, same shape as timetable.json / stations.json.
The demo files are never touched.

What is real and what is derived:
- Real: route numbers (route_short_name), stop names, trip departure/arrival times,
  GTFS trip ids.
- Stations: the terminals (first/last stop) of the trips, grouped by DHID stop area
  (de:09564:510:2:3 -> de:09564:510), so all platforms of a stop are one station.
  Intermediate stops are not stations because trips in this shape are terminal to terminal.
- distanceKm: straight-line distance x ROAD_FACTOR (no road network in GTFS).
- Duties, drivers and buses are SYNTHETIC: the feed has no usable block_id, so trips are
  chained into vehicle blocks (same terminal, >= MIN_LAYOVER_MIN layover, same line
  preferred, shortest wait first; no empty repositioning trips) and blocks are cut into
  driver duties of at most MAX_DUTY_MIN. Ids are prefixed RB/RD/RDU to keep them apart from
  the demo's B/D/DU ids.
- Trips running past midnight (GTFS times >= 24:00) are left out: the engines model one
  calendar day.
"""

import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
FILTERED = BACKEND.parent / "data" / "filtered"
OUT_TIMETABLE = BACKEND / "data" / "timetable_real.json"
OUT_STATIONS = BACKEND / "data" / "stations_real.json"

ROAD_FACTOR = 1.35  # same as the demo generator
MIN_LAYOVER_MIN = 5  # shortest turnaround before a bus takes its next trip
MAX_DUTY_MIN = 8 * 60 + 30  # cut a block into a new duty when the span would exceed this
LONG_LAYOVER_MIN = 60  # same thresholds the idle-time engine reports
SPLIT_BREAK_MIN = 120
SHORT_DUTY_MIN = 5 * 60


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def km(a: dict, b: dict) -> float:
    dy = (a["lat"] - b["lat"]) * 111.2
    dx = (a["lng"] - b["lng"]) * 111.2 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))  # symmetric
    return math.hypot(dx, dy)


def stop_area(stop_id: str) -> str:
    """DHID stop area: de:09564:510:2:3 -> de:09564:510 (all platforms of one stop)."""
    return ":".join(stop_id.split(":")[:3])


# --- Load ---------------------------------------------------------------------

def load():
    read = lambda name: pd.read_csv(FILTERED / f"{name}.csv", dtype=str, keep_default_na=False)
    routes, trips, stop_times, stops = read("routes"), read("trips"), read("stop_times"), read("stops")
    stop_times["seq"] = stop_times["stop_sequence"].astype(int)
    ends = (stop_times.sort_values(["trip_id", "seq"]).groupby("trip_id")
            .agg(first_stop=("stop_id", "first"), last_stop=("stop_id", "last"),
                 dep=("departure_time", "first"), arr=("arrival_time", "last")))
    trips = (trips.merge(ends, left_on="trip_id", right_index=True)
             .merge(routes[["route_id", "route_short_name"]], on="route_id"))
    return trips, stops


# --- Stations -----------------------------------------------------------------

def build_stations(trips: pd.DataFrame, stops: pd.DataFrame) -> tuple[list[dict], dict[str, str]]:
    """Terminal stop areas as stations; returns (stations, stop_id -> station name)."""
    stops = stops.assign(area=stops["stop_id"].map(stop_area),
                         lat=stops["stop_lat"].astype(float), lng=stops["stop_lon"].astype(float))
    terminals = set(trips["first_stop"].map(stop_area)) | set(trips["last_stop"].map(stop_area))
    areas = (stops[stops["area"].isin(terminals)].groupby("area")
             .agg(name=("stop_name", lambda s: s.mode().iloc[0]), lat=("lat", "mean"), lng=("lng", "mean")))

    # Names must be unique (the engines key stations by name): disambiguate repeats with the area id.
    counts = Counter(areas["name"])
    areas["name"] = [n if counts[n] == 1 else f"{n} ({area.split(':')[-1]})" for area, n in areas["name"].items()]

    stations = [{"id": area, "name": r["name"], "lat": round(r["lat"], 6), "lng": round(r["lng"], 6)}
                for area, r in areas.sort_values("name").iterrows()]
    name_of_area = areas["name"].to_dict()
    return stations, {sid: name_of_area[stop_area(sid)] for sid in pd.concat([trips["first_stop"], trips["last_stop"]])}


def distance_matrix(stations: list[dict]) -> dict[str, dict[str, float]]:
    return {a["name"]: {b["name"]: 0 if a is b else round(km(a, b) * ROAD_FACTOR, 1) for b in stations}
            for a in stations}


# --- Blocks and duties (synthetic) --------------------------------------------

def chain_blocks(trips: list[dict]) -> list[list[dict]]:
    """Greedy vehicle blocks: a bus waiting at the trip's start terminal takes it; else a new bus."""
    blocks: list[list[dict]] = []
    for trip in sorted(trips, key=lambda t: (t["dep"], t["tripId"])):
        waiting = [b for b in blocks
                   if b[-1]["endStation"] == trip["startStation"] and b[-1]["arr"] + MIN_LAYOVER_MIN <= trip["dep"]]
        if waiting:
            # same line first, then the bus that has waited the shortest time
            best = min(waiting, key=lambda b: (b[-1]["route"] != trip["route"], trip["dep"] - b[-1]["arr"]))
            best.append(trip)
        else:
            blocks.append([trip])
    return blocks


def cut_duties(block: list[dict]) -> list[list[dict]]:
    """Split a block into driver duties no longer than MAX_DUTY_MIN (relief at a terminal)."""
    duties, current = [], []
    for trip in block:
        if current and trip["arr"] - current[0]["dep"] > MAX_DUTY_MIN:
            duties.append(current)
            current = []
        current.append(trip)
    return duties + [current]


def duty_type(legs: list[dict]) -> str:
    gaps = [b["dep"] - a["arr"] for a, b in zip(legs, legs[1:])]
    if any(g >= SPLIT_BREAK_MIN for g in gaps):
        return "split"
    if legs[-1]["arr"] - legs[0]["dep"] < SHORT_DUTY_MIN:
        return "short"
    if any(g >= LONG_LAYOVER_MIN for g in gaps):
        return "long-layover"
    return "straight"


# --- Main -----------------------------------------------------------------------

def main():
    trips_df, stops = load()
    meta = json.loads((FILTERED / "meta.json").read_text())
    past_midnight = trips_df[(trips_df["dep"] >= "24") | (trips_df["arr"] >= "24")]
    trips_df = trips_df.drop(past_midnight.index)

    stations, station_of_stop = build_stations(trips_df, stops)
    trips = [{
        "tripId": r["trip_id"],
        "route": r["route_short_name"],
        "startStation": station_of_stop[r["first_stop"]],
        "endStation": station_of_stop[r["last_stop"]],
        "dep": to_min(r["dep"]),
        "arr": to_min(r["arr"]),
    } for _, r in trips_df.iterrows()]

    blocks = chain_blocks(trips)
    duties, out_trips = [], []
    n = 0
    for b_no, block in enumerate(blocks, 1):
        bus = f"RB{b_no:04d}"
        for legs in cut_duties(block):
            n += 1
            duty, driver = f"RDU{n:04d}", f"RD{n:04d}"
            duties.append({
                "dutyId": duty, "driverId": driver, "busId": bus,
                "type": duty_type(legs), "runsOn": ["weekday"],
                "start": to_hhmm(legs[0]["dep"]), "end": to_hhmm(legs[-1]["arr"]),
                "spanMinutes": legs[-1]["arr"] - legs[0]["dep"],
                "drivingMinutes": sum(t["arr"] - t["dep"] for t in legs),
            })
            out_trips += [{
                "tripId": t["tripId"], "route": t["route"],
                "startStation": t["startStation"], "endStation": t["endStation"],
                "departureTime": to_hhmm(t["dep"]), "arrivalTime": to_hhmm(t["arr"]),
                "dutyId": duty, "driverId": driver, "busId": bus,
            } for t in legs]

    timetable = {
        "template": "weekday",
        "duties": duties,
        "trips": out_trips,
        "calendar": [{  # the filtered feed covers a single service day
            "date": meta["serviceDate"], "dayType": "weekday", "holiday": None,
            "activeDuties": len(duties), "driversOnVacation": [], "uncoveredDuties": [],
        }],
    }
    OUT_STATIONS.write_text(json.dumps({"stations": stations, "distanceKm": distance_matrix(stations)},
                                       indent=2, ensure_ascii=False) + "\n")
    OUT_TIMETABLE.write_text(json.dumps(timetable, indent=2, ensure_ascii=False) + "\n")

    types = Counter(d["type"] for d in duties)
    span = sum(d["spanMinutes"] for d in duties)
    print(f"service date: {meta['serviceDate']} (from data/filtered/meta.json)")
    print(f"stations:  {len(stations)} terminals -> {OUT_STATIONS.relative_to(BACKEND)}")
    print(f"trips:     {len(out_trips)} ({len(past_midnight)} past-midnight trips left out)")
    print(f"buses:     {len(blocks)} synthetic vehicle blocks")
    print(f"duties:    {len(duties)} ({', '.join(f'{v} {k}' for k, v in types.most_common())})")
    print(f"utilization (driving / span): {100 * sum(d['drivingMinutes'] for d in duties) / span:.1f}%")
    print(f"-> {OUT_TIMETABLE.relative_to(BACKEND)}")


if __name__ == "__main__":
    main()
