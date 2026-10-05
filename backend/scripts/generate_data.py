"""Generate the hardcoded MVP dataset in backend/data/.

Run from backend/:  python scripts/generate_data.py

Everything is derived from the small specs below, so the files stay
consistent with each other (bus ids, stations, route times, vacations).
The weekday timetable is deliberately inefficient - split shifts, long
terminal layovers and uneven duty lengths - so there is idle time to find.
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# --- Stations -----------------------------------------------------------

STATIONS = [
    {"id": "CEN", "name": "Central Station", "lat": 49.4459, "lng": 11.0825},
    {"id": "AIR", "name": "Airport", "lat": 49.4987, "lng": 11.0780},
    {"id": "NOR", "name": "North Station", "lat": 49.4760, "lng": 11.1050},
    {"id": "SOU", "name": "South Station", "lat": 49.4180, "lng": 11.1000},
    {"id": "UNI", "name": "University", "lat": 49.4330, "lng": 11.0350},
]
ROAD_FACTOR = 1.35  # road distance vs straight line


def straight_km(a, b):
    dy = (a["lat"] - b["lat"]) * 111.2
    dx = (a["lng"] - b["lng"]) * 111.2 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


def distance_matrix():
    return {
        a["name"]: {
            b["name"]: 0 if a is b else max(1, round(straight_km(a, b) * ROAD_FACTOR))
            for b in STATIONS
        }
        for a in STATIONS
    }


# --- Routes ---------------------------------------------------------------

def round5(x):
    return int(5 * round(x / 5))


# One regular route per station pair (5 stations -> 10 pairs).
ROUTE_PAIRS = [
    ("R1", "Central Station", "Airport"),
    ("R2", "Central Station", "North Station"),
    ("R3", "Central Station", "South Station"),
    ("R4", "Central Station", "University"),
    ("R5", "Airport", "North Station"),
    ("R6", "Airport", "South Station"),
    ("R7", "Airport", "University"),
    ("R8", "North Station", "South Station"),
    ("R9", "North Station", "University"),
    ("R10", "South Station", "University"),
]

# Candidate express services for the optimizer (POST /optimize).
# (id, start, end, headwayMin, serviceStart, serviceEnd). Each departure from
# `start` is a round trip: out, turnaround at `end`, back to `start`.
EXPRESS = [
    ("E1", "Central Station", "Airport", 60, "09:30", "12:30"),
    ("E2", "University", "Central Station", 30, "09:30", "13:30"),
    ("E3", "North Station", "South Station", 60, "09:00", "12:00"),
]
EXPRESS_TURNAROUND_MIN = 10


def build_routes(dist):
    routes = []
    for rid, a, b in ROUTE_PAIRS:
        km = dist[a][b]
        routes.append({
            "routeId": rid,
            "name": f"{a} - {b}",
            "from": a,
            "to": b,
            "distanceKm": km,
            "durationMin": round5(km * 3 + 20),  # all-stops service
            "frequencyMin": 30 if rid in ("R1", "R2", "R3", "R4") else 60,
        })
    express = []
    for eid, a, b, headway, first, last in EXPRESS:
        km = dist[a][b]
        express.append({
            "routeId": eid,
            "name": f"{a} - {b} Express",
            "startStation": a,
            "endStation": b,
            "distanceKm": km,
            "tripDurationMin": round5(km * 2 + 5),  # few stops
            "turnaroundMin": EXPRESS_TURNAROUND_MIN,
            "headwayMin": headway,
            "serviceStart": first,
            "serviceEnd": last,
        })
    return {"routes": routes, "expressCandidates": express}


# --- Drivers ----------------------------------------------------------------

# (driverId, homeStation, overtimeAvailable, maxShiftHours, vacation (first, last) or None)
DRIVERS = [
    ("D001", "Central Station", True, 10, None),
    ("D002", "Central Station", True, 10, None),
    ("D003", "Central Station", False, 10, None),
    ("D004", "Central Station", True, 8, ("2026-10-12", "2026-10-14")),
    ("D005", "Central Station", True, 10, None),
    ("D006", "Central Station", False, 9, None),
    ("D007", "Airport", True, 10, None),
    ("D008", "Airport", False, 10, None),
    ("D009", "Airport", True, 10, ("2026-10-19", "2026-10-23")),
    ("D010", "Airport", True, 8, None),
    ("D011", "North Station", True, 10, None),
    ("D012", "North Station", False, 9, None),
    ("D013", "North Station", True, 10, ("2026-10-28", "2026-10-30")),
    ("D014", "North Station", True, 8, ("2026-10-21", "2026-10-23")),
    ("D015", "South Station", True, 10, None),
    ("D016", "South Station", False, 10, None),
    ("D017", "South Station", True, 10, None),
    ("D018", "University", True, 10, None),
    ("D019", "University", False, 8, ("2026-10-22", "2026-10-23")),
    ("D020", "University", True, 9, None),
]


def date_range(first, last):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    out = []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def build_drivers():
    return [
        {
            "driverId": did,
            "homeStation": home,
            "overtimeAvailable": ot,
            "maxShiftHours": max_h,
            "vacationDates": date_range(*vac) if vac else [],
        }
        for did, home, ot, max_h, vac in DRIVERS
    ]


# --- Buses ------------------------------------------------------------------

# Buses are numbered in blocks per home depot. 50 buses, only 20 drivers:
# the whole point of the challenge.
BUS_BLOCKS = [
    ("Central Station", 1, 16),
    ("Airport", 17, 21),
    ("North Station", 22, 31),
    ("South Station", 32, 41),
    ("University", 42, 50),
]
MAINTENANCE = {"B003", "B017", "B025", "B046"}
ARTICULATED = {"B001", "B002", "B018", "B019", "B032"}  # high-demand airport/central lines
MIDI = {"B048", "B049", "B050"}


def bus_type(bid):
    if bid in ARTICULATED:
        return "articulated", 120
    if bid in MIDI:
        return "midi", 50
    return "standard", 80


# --- Weekday timetable ------------------------------------------------------

# Each duty starts and ends at the driver's home station.
# block = (routeId, firstDeparture, roundTrips, layoverAway, layoverHome)
# Gaps between blocks are split-shift breaks; big layovers are idle at a terminal.
DUTIES = [
    # driver, bus, type, runsOn, blocks
    ("D001", "B001", "straight", "daily", [("R1", "06:00", 4, 10, 10)]),
    ("D002", "B002", "split", "weekday", [("R2", "06:30", 2, 10, 10), ("R2", "12:30", 2, 10, 10)]),
    ("D003", "B004", "long-layover", "daily", [("R3", "07:00", 4, 60, 10)]),
    ("D004", "B005", "short", "weekday", [("R4", "07:00", 3, 10, 10)]),
    ("D005", "B006", "split", "weekday", [("R1", "06:15", 2, 10, 10), ("R1", "12:45", 2, 10, 10)]),
    ("D006", "B007", "straight", "daily", [("R4", "11:30", 5, 10, 10)]),
    ("D007", "B018", "split", "weekday", [("R1", "05:45", 2, 10, 10), ("R1", "12:15", 2, 10, 10)]),
    ("D008", "B019", "long-layover", "daily", [("R5", "06:00", 4, 10, 75)]),
    ("D009", "B020", "straight", "daily", [("R6", "06:30", 3, 10, 10)]),
    ("D010", "B021", "short", "weekday", [("R7", "09:30", 2, 10, 10)]),
    ("D011", "B022", "split", "weekday", [("R2", "06:00", 2, 10, 10), ("R8", "12:30", 2, 10, 10)]),
    ("D012", "B023", "straight", "daily", [("R8", "06:30", 4, 10, 10)]),
    ("D013", "B024", "long-layover", "daily", [("R9", "07:00", 3, 60, 10)]),
    ("D014", "B026", "short", "weekday", [("R5", "14:00", 3, 10, 10)]),
    ("D015", "B032", "split", "weekday", [("R3", "06:00", 3, 10, 10), ("R10", "12:50", 2, 10, 10)]),
    ("D016", "B033", "straight", "daily", [("R6", "07:00", 3, 10, 10)]),
    ("D017", "B034", "long-layover", "daily", [("R10", "07:30", 3, 65, 10)]),
    ("D018", "B042", "split", "weekday", [("R4", "06:30", 2, 10, 10), ("R4", "12:30", 2, 10, 10)]),
    ("D019", "B043", "short", "weekday", [("R10", "11:00", 3, 10, 10)]),
    ("D020", "B044", "straight", "daily", [("R7", "06:00", 3, 10, 10)]),
]
RUNS_ON = {
    "daily": ["weekday", "saturday", "sunday"],
    "weekday": ["weekday"],
}


def to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def build_timetable(routes_by_id, home_of):
    trips, duties = [], []
    trip_no = 1
    for did, bus, dtype, runs_on, blocks in DUTIES:
        home = home_of[did]
        duty_id = f"DU{did[1:]}"
        duty_trips = []
        for rid, first_dep, rts, lay_away, lay_home in blocks:
            r = routes_by_id[rid]
            away = r["to"] if r["from"] == home else r["from"]
            assert home in (r["from"], r["to"]), (did, rid)
            t = to_min(first_dep)
            for i in range(rts):
                for start, end in ((home, away), (away, home)):
                    arr = t + r["durationMin"]
                    duty_trips.append({
                        "tripId": f"T{trip_no:03d}",
                        "route": rid,
                        "startStation": start,
                        "endStation": end,
                        "departureTime": to_hhmm(t),
                        "arrivalTime": to_hhmm(arr),
                        "dutyId": duty_id,
                        "driverId": did,
                        "busId": bus,
                    })
                    trip_no += 1
                    t = arr + (lay_away if end == away else lay_home)
        trips.extend(duty_trips)
        start, end = duty_trips[0]["departureTime"], duty_trips[-1]["arrivalTime"]
        driving = sum(to_min(x["arrivalTime"]) - to_min(x["departureTime"]) for x in duty_trips)
        duties.append({
            "dutyId": duty_id,
            "driverId": did,
            "busId": bus,
            "type": dtype,
            "runsOn": RUNS_ON[runs_on],
            "start": start,
            "end": end,
            "spanMinutes": to_min(end) - to_min(start),
            "drivingMinutes": driving,
        })
    return trips, duties


# --- 30-day calendar --------------------------------------------------------

CALENDAR_START = date(2026, 10, 1)
CALENDAR_DAYS = 30
HOLIDAYS = {"2026-10-03": "Tag der Deutschen Einheit"}


def build_calendar(drivers, duties):
    cal = []
    for i in range(CALENDAR_DAYS):
        d = CALENDAR_START + timedelta(days=i)
        iso = d.isoformat()
        if iso in HOLIDAYS or d.weekday() == 6:
            day_type = "sunday"
        elif d.weekday() == 5:
            day_type = "saturday"
        else:
            day_type = "weekday"
        on_vacation = [x["driverId"] for x in drivers if iso in x["vacationDates"]]
        active = [x for x in duties if day_type in x["runsOn"]]
        uncovered = [x["dutyId"] for x in active if x["driverId"] in on_vacation]
        cal.append({
            "date": iso,
            "dayType": day_type,
            "holiday": HOLIDAYS.get(iso),
            "activeDuties": len(active),
            "driversOnVacation": on_vacation,
            "uncoveredDuties": uncovered,
        })
    return cal


# --- Main -------------------------------------------------------------------

def write(name, payload):
    path = DATA_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(DATA_DIR.parent)}")


def main():
    dist = distance_matrix()
    routes = build_routes(dist)
    routes_by_id = {r["routeId"]: r for r in routes["routes"]}
    drivers = build_drivers()
    home_of = {d["driverId"]: d["homeStation"] for d in drivers}

    trips, duties = build_timetable(routes_by_id, home_of)
    active_buses = {d["busId"] for d in duties}

    buses = []
    for station, first, last in BUS_BLOCKS:
        for n in range(first, last + 1):
            bid = f"B{n:03d}"
            btype, cap = bus_type(bid)
            status = "maintenance" if bid in MAINTENANCE else "active" if bid in active_buses else "spare"
            buses.append({"busId": bid, "station": station, "status": status, "type": btype, "capacity": cap})

    write("stations.json", {"stations": STATIONS, "distanceKm": dist})
    write("routes.json", routes)
    write("drivers.json", {"drivers": drivers})
    write("buses.json", {"buses": buses})
    write("timetable.json", {
        "template": "weekday",
        "duties": duties,
        "trips": trips,
        "calendar": build_calendar(drivers, duties),
    })


if __name__ == "__main__":
    main()
