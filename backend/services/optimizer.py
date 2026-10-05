"""POST /optimize: test candidate express routes with the CP-SAT model and recommend a launch plan.

Each candidate is solved on its own against today's roster. A candidate is
feasible when every trip is covered by existing drivers (idle time or allowed
overtime) with a spare bus, i.e. 0 new drivers. The recommended plan then adds
feasible routes one by one and re-solves them together, so two routes never
count on the same idle minutes.

All CP-SAT solves of one request share a time budget (OPTIMIZE_TIME_LIMIT_S, default 8 s). If a solve
doesn't finish with a proven-optimal answer in time, or fails, the last good result for the same data
source, date and options is returned with `cached: true`; without one, the request fails with 503.
"""

import logging
import os
import time

import config
from errors import ApiError
from schemas.optimize import OptimizeRequest, OptimizeResponse, RouteResult, TripAssignment
from services import data
from services.express_model import Solution, build_driver_days, build_tasks, solve
from services.idle import idle_windows
from services.time_utils import hours, to_hhmm, tomorrow


def _candidates(req: OptimizeRequest) -> list[dict]:
    if not req.candidates:
        return data.express_candidates()
    out = []
    for i, c in enumerate(req.candidates, 1):
        cand = c.model_dump(by_alias=True)
        data.require_station(cand["startStation"])
        data.require_station(cand["endStation"])
        cand["routeId"] = cand["routeId"] or f"X{i}"
        cand["name"] = cand["name"] or f"{cand['startStation']} - {cand['endStation']} Express"
        out.append(cand)
    return out


def _reason(cand: dict, sol: Solution, spare: dict[str, int]) -> str:
    n = len(sol.assignments)
    if n == 0:
        return "No departures in the service window"
    if sol.covered == n and sol.new_drivers == 0:
        drivers = sorted({a.driver_id for a in sol.assignments})
        text = f"All {n} trips covered by {', '.join(drivers)}"
        return text + (f" with {hours(sol.overtime_minutes)} h overtime" if sol.overtime_minutes else " from idle time")
    parts = []
    if sol.new_drivers:
        parts.append(f"{sol.new_drivers} new driver(s) needed for {sum(a.kind == 'new-driver' for a in sol.assignments)} trip(s)")
    if sol.covered < n:
        bus_note = f"only {spare[cand['startStation']]} spare bus(es) at {cand['startStation']}"
        parts.append(f"{n - sol.covered} trip(s) uncovered ({bus_note})")
    return "; ".join(parts)


def _route_result(cand: dict, sol: Solution, spare: dict[str, int]) -> RouteResult:
    n = len(sol.assignments)
    return RouteResult(
        route=cand["routeId"],
        name=cand["name"],
        start_station=cand["startStation"],
        end_station=cand["endStation"],
        trips_requested=n,
        trips_covered=sol.covered,
        feasible=n > 0 and sol.covered == n and sol.new_drivers == 0,
        new_drivers_required=sol.new_drivers,
        idle_hours_used=hours(sol.idle_minutes_used),
        overtime_hours_used=hours(sol.overtime_minutes),
        utilization_before=sol.utilization_before,
        utilization_after=sol.utilization_after,
        reason=_reason(cand, sol, spare),
        assignments=[
            TripAssignment(trip_id=a.task.task_id, departure=to_hhmm(a.task.start), returns_at=to_hhmm(a.task.end),
                           driver=a.driver_id, kind=a.kind)
            for a in sol.assignments
        ],
    )


log = logging.getLogger(__name__)

TIME_LIMIT_ENV = "OPTIMIZE_TIME_LIMIT_S"
DEFAULT_TIME_LIMIT_S = 8.0

# (data source, date, request options) -> last result that solved to optimality
_last_good: dict[tuple[str, str, str], OptimizeResponse] = {}


class SolveIncomplete(Exception):
    """A solve ran out of time or didn't prove optimality."""


def time_limit_s() -> float:
    raw = os.getenv(TIME_LIMIT_ENV, "").strip()
    try:
        value = float(raw) if raw else DEFAULT_TIME_LIMIT_S
    except ValueError:
        value = 0
    if value <= 0:
        log.warning("%s=%r is not a positive number of seconds; using %s", TIME_LIMIT_ENV, raw, DEFAULT_TIME_LIMIT_S)
        return DEFAULT_TIME_LIMIT_S
    return value


def clear_cache() -> None:
    _last_good.clear()


def optimize(req: OptimizeRequest) -> OptimizeResponse:
    # Validation (unknown station, bad date) raises 4xx here, before any solving.
    day = data.resolve_day(req.date, default=tomorrow())
    candidates = _candidates(req)
    key = (config.DATA_SOURCE, day.date, req.model_dump_json(exclude={"date"}))
    try:
        result = _solve_all(day, req, candidates, deadline=time.perf_counter() + time_limit_s())
    except ApiError:
        raise
    except Exception as e:  # timeout, or anything the solver threw
        cached = _last_good.get(key)
        log.warning("optimize %s on %s failed (%s); %s", config.DATA_SOURCE, day.date, e,
                    "returning the cached result" if cached else "no cached result")
        if cached:
            return cached.model_copy(update={"cached": True})
        raise ApiError(503, "OPTIMIZE_UNAVAILABLE",
                       f"Optimization didn't finish ({e}) and there is no earlier result for {day.date} to fall back on")
    _last_good[key] = result
    return result


def _solve_all(day: data.Day, req: OptimizeRequest, candidates: list[dict], deadline: float) -> OptimizeResponse:
    drivers = build_driver_days(day, req.allow_overtime)
    spare = {s: len(data.spare_buses(s)) for s in data.station_names()}
    tasks = {c["routeId"]: build_tasks(c) for c in candidates}

    def solve_in_budget(route_tasks):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise SolveIncomplete(f"time limit of {time_limit_s():g} s reached")
        sol = solve(route_tasks, drivers, spare, time_limit_s=remaining)
        if sol.status != "OPTIMAL":
            raise SolveIncomplete(f"solver stopped with status {sol.status}")
        return sol

    results = [_route_result(c, solve_in_budget(tasks[c["routeId"]]), spare) for c in candidates]

    # Launch plan: cheapest feasible routes first; keep a route only if the combined model still needs nobody new.
    plan_routes: list[str] = []
    plan = solve_in_budget([])
    for r in sorted((r for r in results if r.feasible), key=lambda r: (r.overtime_hours_used, -r.trips_covered)):
        trial = solve_in_budget([t for rid in plan_routes + [r.route] for t in tasks[rid]])
        if trial.covered == len(trial.assignments) and trial.new_drivers == 0:
            plan_routes.append(r.route)
            plan = trial

    if plan_routes:
        summary = (f"Launch {', '.join(plan_routes)} with existing drivers: {plan.covered} express trips, "
                   f"{hours(plan.idle_minutes_used)} idle h and {hours(plan.overtime_minutes)} overtime h used, "
                   f"utilization {plan.utilization_before}% -> {plan.utilization_after}%.")
    else:
        summary = "No candidate can be covered by existing drivers alone."
    rejected = [r for r in results if r.route not in plan_routes]
    if rejected:
        summary += " Not recommended: " + "; ".join(f"{r.route} ({r.reason})" for r in rejected) + "."

    return OptimizeResponse(
        date=day.date,
        allow_overtime=req.allow_overtime,
        current_utilization=plan.utilization_before,
        optimized_utilization=plan.utilization_after,
        total_idle_hours_available=hours(sum(w.minutes for w in idle_windows(day))),
        total_idle_hours_used=hours(plan.idle_minutes_used),
        overtime_hours_used=hours(plan.overtime_minutes),
        new_drivers_required=sum(r.new_drivers_required for r in results),
        recommended=plan_routes,
        summary=summary,
        recommendations=results,
    )
