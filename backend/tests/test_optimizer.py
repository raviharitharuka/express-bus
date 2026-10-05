"""Checks the CP-SAT optimizer against the rules independently of the solver.

Run from backend/:  python -m pytest -q
"""

from services import data
from services.express_model import (
    BREAK_WINDOW_MIN, MAX_DRIVING_IN_WINDOW_MIN, DriverDay, Slot, Task, solve,
)
from services.optimizer import optimize
from schemas.optimize import ExpressCandidate, OptimizeRequest
from services.time_utils import to_min

DATE = "2026-10-06"
TURNAROUND = 10  # all candidates use the default turnaround


def _check_rules(res, date):
    """Every assignment respects overlap, station, max-shift, break and overtime rules."""
    day = data.resolve_day(date)
    drivers = data.drivers()
    trips = data.trips_by_duty()
    duty_of = {d["driverId"]: d for d in day.working_duties()}
    for r in res.recommendations:
        per_driver: dict[str, list] = {}
        for a in r.assignments:
            if a.driver and not a.driver.startswith("NEW-"):
                per_driver.setdefault(a.driver, []).append((to_min(a.departure), to_min(a.returns_at)))
        for did, tasks in per_driver.items():
            assert did in duty_of, f"{did} is not working on {date}"
            legs = trips[duty_of[did]["dutyId"]]
            existing = [(to_min(t["departureTime"]), to_min(t["arrivalTime"])) for t in legs]
            busy = sorted(existing + tasks)
            assert all(a[1] <= b[0] for a, b in zip(busy, busy[1:])), f"{did} double-booked"
            span = busy[-1][1] - busy[0][0]
            assert span <= drivers[did]["maxShiftHours"] * 60, f"{did} exceeds max shift"
            rostered = existing[-1][1] - existing[0][0]
            if span > rostered:
                assert res.allow_overtime and drivers[did]["overtimeAvailable"], f"{did} overtime not allowed"
            for s, _ in tasks:  # driver stands at the start station when the task begins
                before = [t for t in legs if to_min(t["arrivalTime"]) <= s]
                where = before[-1]["endStation"] if before else legs[0]["startStation"]
                assert where == r.start_station, f"{did} is at {where}, not {r.start_station}"
            dur = (tasks[0][1] - tasks[0][0] - TURNAROUND) // 2  # round trip = out + turnaround + back
            driving = existing + [iv for s, e in tasks for iv in ((s, s + dur), (e - dur, e))]
            for w in range(busy[0][0] - BREAK_WINDOW_MIN, busy[-1][1], 5):
                used = sum(max(0, min(e, w + BREAK_WINDOW_MIN) - max(s, w)) for s, e in driving)
                assert used <= MAX_DRIVING_IN_WINDOW_MIN, f"{did} breaks the driving rule"


def test_default_candidates_and_recommendation():
    res = optimize(OptimizeRequest(date=DATE))
    by_route = {r.route: r for r in res.recommendations}
    assert by_route["E1"].feasible and by_route["E3"].feasible
    assert not by_route["E2"].feasible and by_route["E2"].new_drivers_required >= 1
    assert set(res.recommended) == {"E1", "E3"}
    assert res.optimized_utilization > res.current_utilization
    _check_rules(res, DATE)


def test_without_overtime():
    res = optimize(OptimizeRequest(date=DATE, allow_overtime=False))
    assert res.overtime_hours_used == 0
    assert all(a.kind != "overtime" for r in res.recommendations for a in r.assignments)
    _check_rules(res, DATE)


def test_vacation_drivers_are_not_used():
    date = "2026-10-28"  # D013 on vacation
    res = optimize(OptimizeRequest(date=date))
    assert all(a.driver != "D013" for r in res.recommendations for a in r.assignments)
    _check_rules(res, date)


def test_no_spare_bus_means_uncovered():
    cand = ExpressCandidate(start_station="Airport", end_station="North Station", headway_min=60,
                            service_start="09:00", service_end="12:00", trip_duration_min=15)
    res = optimize(OptimizeRequest(date=DATE, candidates=[cand]))
    r = res.recommendations[0]
    assert r.trips_covered == 0 and not r.feasible and "spare bus" in r.reason


def test_break_rule_blocks_assignment():
    # 4 h of continuous driving, then idle at X. A task right away would mean 4h40 driving in 5 h.
    driver = DriverDay("D900", duty_start=360, duty_end=900, max_shift=600, overtime_ok=False,
                       driving=[(360, 600), (840, 900)], slots=[Slot("X", 600, 840, "idle")])
    now = Task("T-now", "R", "X", 600, 650, [(600, 620), (630, 650)])
    later = Task("T-later", "R", "X", 640, 690, [(640, 660), (670, 690)])
    sol = solve([now], [driver], {"X": 1}, time_limit_s=5)
    assert sol.assignments[0].driver_id != "D900"
    sol = solve([later], [driver], {"X": 1}, time_limit_s=5)
    assert sol.assignments[0].driver_id == "D900"
