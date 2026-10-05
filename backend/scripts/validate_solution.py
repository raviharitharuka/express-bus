"""Independently verify an /optimize assignment table against the scheduling rules.

Run from backend/:
    python scripts/validate_solution.py                         # both data sources, overtime on and off
    python scripts/validate_solution.py --source gtfs --date 2026-07-01
    python scripts/validate_solution.py --input result.json --source synthetic   # a saved /optimize response

The checks read only the raw data files (timetable, drivers, routes) and re-implement every rule;
nothing here uses the solver (services/express_model.py). Services are only used to produce a
result when no --input is given. Admin overrides on a running server are not visible to this script,
so validate saved responses that were made without overrides.

Rules (thresholds from API_CONTRACT.md, section 2):
  no overlap      a driver's express trips never overlap each other or their scheduled trips
  max shift       duty span <= maxShiftHours (new hires: 8 h)
  break rule      <= 4.5 h driving in any rolling 5 h window
  vacation        assigned drivers have a duty that day and aren't on vacation
  overtime        a duty is only extended if the request allows overtime and the driver accepts it
  start station   the driver is at the express trip's start station when it leaves and when it returns
Exit code 1 if any rule fails.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MAX_DRIVING_IN_WINDOW_MIN = 270
BREAK_WINDOW_MIN = 300
NEW_HIRE_MAX_SHIFT_MIN = 8 * 60
DEFAULT_TURNAROUND_MIN = 10  # for custom candidates that aren't in routes.json
SHOW_VIOLATIONS = 5

RULES = ["no overlap", "max shift", "break rule", "vacation", "overtime", "start station"]


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


# --- Raw data (no services) ---------------------------------------------------

def load_raw(source: str) -> dict:
    from services.data import DATA_DIR, DATA_FILES  # file names only
    read = lambda name: json.loads((DATA_DIR / DATA_FILES[source][name]).read_text())
    timetable, drivers, routes = read("timetable.json"), read("drivers.json"), read("routes.json")
    trips: dict[str, list[dict]] = {}
    for t in timetable["trips"]:
        trips.setdefault(t["driverId"], []).append(t)
    for legs in trips.values():
        legs.sort(key=lambda t: to_min(t["departureTime"]))
    return {
        "duties": {d["driverId"]: d for d in timetable["duties"]},
        "trips": trips,
        "calendar": {c["date"]: c for c in timetable["calendar"]},
        "drivers": {d["driverId"]: d for d in drivers["drivers"]},
        "candidates": {c["routeId"]: c for c in routes["expressCandidates"]},
    }


def day_type(raw: dict, iso: str) -> str:
    if iso in raw["calendar"]:
        return raw["calendar"][iso]["dayType"]
    wd = date.fromisoformat(iso).weekday()
    return "sunday" if wd == 6 else "saturday" if wd == 5 else "weekday"


# --- Checks -------------------------------------------------------------------

def validate(result: dict, raw: dict) -> dict[str, list[str]]:
    """rule -> violations (empty list = PASS)."""
    violations = {rule: [] for rule in RULES}
    iso, allow_ot, dtype = result["date"], result["allowOvertime"], day_type(raw, result["date"])

    # driver -> [(route, start station, departure, returns, one-way minutes)]
    tasks: dict[str, list[tuple]] = {}
    for rec in result["recommendations"]:
        cand = raw["candidates"].get(rec["route"])
        for a in rec["assignments"]:
            if not a["driver"]:
                continue
            dep, ret = to_min(a["departure"]), to_min(a["returnsAt"])
            turn = cand["turnaroundMin"] if cand else DEFAULT_TURNAROUND_MIN
            one_way = cand["tripDurationMin"] if cand else (ret - dep - turn) // 2
            tasks.setdefault(a["driver"], []).append((a["tripId"], rec["startStation"], dep, ret, one_way))

    for driver, mine in tasks.items():
        new_hire = driver.startswith("NEW-")
        legs = [] if new_hire else raw["trips"].get(driver, [])
        existing = [(to_min(t["departureTime"]), to_min(t["arrivalTime"])) for t in legs]
        express = [(dep, ret) for _, _, dep, ret, _ in mine]

        # vacation: a real driver must have a duty that day and not be on vacation
        if not new_hire:
            drv, duty = raw["drivers"].get(driver), raw["duties"].get(driver)
            if not drv or not duty:
                violations["vacation"].append(f"{driver}: unknown driver or no duty")
                continue
            if iso in drv["vacationDates"]:
                violations["vacation"].append(f"{driver}: on vacation on {iso}")
            if dtype not in duty["runsOn"]:
                violations["vacation"].append(f"{driver}: duty doesn't run on a {dtype}")

        # no overlap
        busy = sorted(existing + express)
        for (s1, e1), (s2, e2) in zip(busy, busy[1:]):
            if s2 < e1:
                violations["no overlap"].append(f"{driver}: {s1 // 60:02d}:{s1 % 60:02d} trip overlaps the next one")

        # max shift and overtime
        span = busy[-1][1] - busy[0][0]
        limit = NEW_HIRE_MAX_SHIFT_MIN if new_hire else round(raw["drivers"][driver]["maxShiftHours"] * 60)
        if span > limit:
            violations["max shift"].append(f"{driver}: span {span} min > {limit} min")
        if not new_hire:
            rostered = existing[-1][1] - existing[0][0]
            if span > rostered and not (allow_ot and raw["drivers"][driver]["overtimeAvailable"]):
                why = "request disallows overtime" if not allow_ot else "driver doesn't accept overtime"
                violations["overtime"].append(f"{driver}: duty extended by {span - rostered} min but {why}")

        # break rule: the busiest 5 h window starts where some driving starts
        driving = existing + [iv for _, _, dep, ret, ow in mine for iv in ((dep, dep + ow), (ret - ow, ret))]
        for w in sorted({s for s, _ in driving}):
            used = sum(max(0, min(e, w + BREAK_WINDOW_MIN) - max(s, w)) for s, e in driving)
            if used > MAX_DRIVING_IN_WINDOW_MIN:
                violations["break rule"].append(f"{driver}: {used} min driving in the 5 h from {w // 60:02d}:{w % 60:02d}")
                break

        # start station: where the driver is when the express trip leaves and when it's back
        if not new_hire:
            for trip_id, station, dep, ret, _ in mine:
                before = [t for t in legs if to_min(t["arrivalTime"]) <= dep]
                after = [t for t in legs if to_min(t["departureTime"]) >= ret]
                at_dep = before[-1]["endStation"] if before else legs[0]["startStation"]
                next_from = after[0]["startStation"] if after else station  # nothing scheduled after: free
                if at_dep != station:
                    violations["start station"].append(f"{trip_id} ({driver}): driver is at {at_dep}, trip leaves {station}")
                if next_from != station:
                    violations["start station"].append(f"{trip_id} ({driver}): back at {station}, next trip leaves {next_from}")
    return violations


def report(label: str, result: dict, violations: dict[str, list[str]]) -> bool:
    assigned = [a for r in result["recommendations"] for a in r["assignments"] if a["driver"]]
    drivers = {a["driver"] for a in assigned}
    hires = {d for d in drivers if d.startswith("NEW-")}
    print(f"\n{label}: {result['date']}, allowOvertime={result['allowOvertime']}, {len(assigned)} assigned trips, "
          f"{len(drivers) - len(hires)} drivers + {len(hires)} new hires")
    ok = True
    for rule in RULES:
        found = violations[rule]
        ok &= not found
        print(f"  {'PASS' if not found else 'FAIL'}  {rule}" + (f" ({len(found)})" if found else ""))
        for v in found[:SHOW_VIOLATIONS]:
            print(f"        {v}")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", choices=["synthetic", "gtfs", "both"], default="both")
    parser.add_argument("--date", help="service date YYYY-MM-DD (default: /optimize's default, tomorrow)")
    parser.add_argument("--input", help="saved /optimize response (JSON) to check instead of running /optimize")
    args = parser.parse_args()

    if args.input:
        source = "synthetic" if args.source == "both" else args.source
        result = json.loads(Path(args.input).read_text())
        sys.exit(0 if report(f"{args.input} [{source}]", result, validate(result, load_raw(source))) else 1)

    from schemas.optimize import OptimizeRequest
    from services import data
    from services.optimizer import optimize

    ok = True
    for source in (["synthetic", "gtfs"] if args.source == "both" else [args.source]):
        data.switch_source(source)
        raw = load_raw(source)
        for allow_ot in (True, False):
            result = optimize(OptimizeRequest(date=args.date, allow_overtime=allow_ot)).model_dump(by_alias=True)
            ok &= report(f"[{source}]", result, validate(result, raw))
    print("\nALL RULES PASS" if ok else "\nSOME RULES FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
