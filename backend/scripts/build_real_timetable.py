"""Convert the filtered VGN GTFS data into the demo's timetable/stations JSON shape.

Run from backend/ after scripts/filter_gtfs.py:
    python scripts/build_real_timetable.py

Reads data/filtered/*.csv and meta.json (repo root) and writes backend/data/*_real.json:
timetable, stations, drivers, buses and routes, each in the same shape as the demo file
without the suffix. The demo files are never touched. Select them with DATA_SOURCE=real.

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
  the demo's B/D/DU ids. Drivers are based at the station where their duty starts, accept
  overtime 2 in 3 times, max shift 9 h, no vacations. Each block is one active bus parked at
  its first terminal, plus a RESERVE_SHARE of spare buses at the busiest terminals.
- Express candidates: the 3 terminals with the most midday idle driver time, each linked to
  the busiest other terminal (every 30 min, 09:00-13:00).
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
OUT_DRIVERS = BACKEND / "data" / "drivers_real.json"
OUT_BUSES = BACKEND / "data" / "buses_real.json"
OUT_ROUTES = BACKEND / "data" / "routes_real.json"

ROAD_FACTOR = 1.35  # same as the demo generator
MIN_LAYOVER_MIN = 5  # shortest turnaround before a bus takes its next trip
MAX_DUTY_MIN = 8 * 60 + 30  # cut a block into a new duty when the span would exceed this
LONG_LAYOVER_MIN = 60  # same thresholds the idle-time engine reports
SPLIT_BREAK_MIN = 120
SHORT_DUTY_MIN = 5 * 60
MAX_SHIFT_HOURS = 9  # duties are cut at 8.5 h, so every driver has some room
RESERVE_SHARE = 0.10  # spare buses on top of the active ones
RESERVE_TERMINALS = 10  # spread them over the busiest terminals
EXPRESS_WINDOW = ("09:00", "13:00")
EXPRESS_HEADWAY_MIN = 30


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
             .merge(routes[["route_id", "route_short_name", "route_long_name"]], on="route_id"))
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


# --- Drivers, buses, routes (synthetic around the real trips) ------------------

def round5(x: float) -> int:
    return int(5 * round(x / 5))


def build_drivers(duties: list[dict], first_station: dict[str, str]) -> list[dict]:
    return [{
        "driverId": d["driverId"],
        "homeStation": first_station[d["dutyId"]],
        "overtimeAvailable": i % 3 != 0,
        "maxShiftHours": MAX_SHIFT_HOURS,
        "vacationDates": [],
    } for i, d in enumerate(duties, 1)]


def build_buses(blocks: list[list[dict]], departures: Counter) -> list[dict]:
    buses = [{"busId": f"RB{i:04d}", "station": b[0]["startStation"], "status": "active",
              "type": "standard", "capacity": 80} for i, b in enumerate(blocks, 1)]
    busiest = [s for s, _ in departures.most_common(RESERVE_TERMINALS)]
    for k in range(math.ceil(len(blocks) * RESERVE_SHARE)):
        buses.append({"busId": f"RB{len(blocks) + k + 1:04d}", "station": busiest[k % len(busiest)],
                      "status": "spare", "type": "standard", "capacity": 80})
    return buses


def midday_idle_by_station(out_trips: list[dict]) -> Counter:
    """Minutes of >= LONG_LAYOVER_MIN gaps inside duties during the express window, per station."""
    lo, hi = (to_min(t) for t in EXPRESS_WINDOW)
    by_duty: dict[str, list[dict]] = {}
    for t in out_trips:
        by_duty.setdefault(t["dutyId"], []).append(t)
    idle = Counter()
    for legs in by_duty.values():
        for a, b in zip(legs, legs[1:]):
            start, end = to_min(a["arrivalTime"]), to_min(b["departureTime"])
            if end - start >= LONG_LAYOVER_MIN:
                idle[a["endStation"]] += max(0, min(end, hi) - max(start, lo))
    return idle


def build_routes(trips_df: pd.DataFrame, trips: list[dict], out_trips: list[dict],
                 dist: dict, departures: Counter) -> dict:
    routes = []
    by_line: dict[str, list[dict]] = {}
    for t in trips:
        by_line.setdefault(t["route"], []).append(t)
    long_names = trips_df.groupby("route_short_name")["route_long_name"].agg(lambda s: s.mode().iloc[0])
    for line in sorted(by_line, key=lambda x: (len(x), x)):
        legs = by_line[line]
        (a, b), _ = Counter((t["startStation"], t["endStation"]) for t in legs).most_common(1)[0]
        main = [t for t in legs if (t["startStation"], t["endStation"]) == (a, b)]
        span = max(t["dep"] for t in main) - min(t["dep"] for t in main)
        routes.append({
            "routeId": line, "name": long_names[line], "from": a, "to": b,
            "distanceKm": dist[a][b],
            "durationMin": int(pd.Series([t["arr"] - t["dep"] for t in main]).median()),
            "frequencyMin": max(5, round5(span / max(1, len(main) - 1))),
        })

    idle = midday_idle_by_station(out_trips)
    express = []
    for i, (start, _) in enumerate(idle.most_common(3), 1):
        end = next(s for s, _ in departures.most_common() if s != start)
        km_ = dist[start][end]
        express.append({
            "routeId": f"E{i}", "name": f"{start} - {end} Express", "startStation": start, "endStation": end,
            "distanceKm": km_, "tripDurationMin": max(10, round5(km_ * 2 + 5)), "turnaroundMin": 10,
            "headwayMin": EXPRESS_HEADWAY_MIN, "serviceStart": EXPRESS_WINDOW[0], "serviceEnd": EXPRESS_WINDOW[1],
        })
    return {"routes": routes, "expressCandidates": express}


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
    dist = distance_matrix(stations)
    departures = Counter(t["startStation"] for t in trips)
    first_station = {d["dutyId"]: next(t["startStation"] for t in out_trips if t["dutyId"] == d["dutyId"])
                     for d in duties}
    drivers = build_drivers(duties, first_station)
    buses = build_buses(blocks, departures)
    routes = build_routes(trips_df, trips, out_trips, dist, departures)

    for path, payload in [(OUT_STATIONS, {"stations": stations, "distanceKm": dist}), (OUT_TIMETABLE, timetable),
                          (OUT_DRIVERS, {"drivers": drivers}), (OUT_BUSES, {"buses": buses}), (OUT_ROUTES, routes)]:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    types = Counter(d["type"] for d in duties)
    span = sum(d["spanMinutes"] for d in duties)
    print(f"service date: {meta['serviceDate']} (from data/filtered/meta.json)")
    print(f"stations:  {len(stations)} terminals -> {OUT_STATIONS.relative_to(BACKEND)}")
    print(f"trips:     {len(out_trips)} ({len(past_midnight)} past-midnight trips left out)")
    print(f"buses:     {len(blocks)} synthetic vehicle blocks")
    print(f"duties:    {len(duties)} ({', '.join(f'{v} {k}' for k, v in types.most_common())})")
    print(f"utilization (driving / span): {100 * sum(d['drivingMinutes'] for d in duties) / span:.1f}%")
    print(f"drivers:   {len(drivers)}, buses: {len(buses)} ({len(buses) - len(blocks)} spare), "
          f"lines: {len(routes['routes'])}")
    print("express candidates: " + "; ".join(f"{e['routeId']} {e['name']}" for e in routes["expressCandidates"]))
    print("-> backend/data/{timetable,stations,drivers,buses,routes}_real.json")


if __name__ == "__main__":
    main()
