"""POST /optimize: test candidate express routes with the CP-SAT model and recommend a launch plan.

Each candidate is solved on its own against today's roster. A candidate is
feasible when every trip is covered by existing drivers (idle time or allowed
overtime) with a spare bus, i.e. 0 new drivers. The recommended plan then adds
feasible routes one by one and re-solves them together, so two routes never
count on the same idle minutes.
"""

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


def optimize(req: OptimizeRequest) -> OptimizeResponse:
    day = data.resolve_day(req.date, default=tomorrow())
    candidates = _candidates(req)
    drivers = build_driver_days(day, req.allow_overtime)
    spare = {s: len(data.spare_buses(s)) for s in data.station_names()}
    tasks = {c["routeId"]: build_tasks(c) for c in candidates}

    results = [_route_result(c, solve(tasks[c["routeId"]], drivers, spare), spare) for c in candidates]

    # Launch plan: cheapest feasible routes first; keep a route only if the combined model still needs nobody new.
    plan_routes: list[str] = []
    plan = solve([], drivers, spare)
    for r in sorted((r for r in results if r.feasible), key=lambda r: (r.overtime_hours_used, -r.trips_covered)):
        trial = solve([t for rid in plan_routes + [r.route] for t in tasks[rid]], drivers, spare)
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
