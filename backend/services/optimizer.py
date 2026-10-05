"""Express route feasibility: staff candidate express trips from idle (and optional overtime) windows."""

import math

from schemas.optimize import OptimizeRequest, OptimizeResponse, RouteRecommendation
from services import data
from services.idle import Window, driver_utilization, express_round_trip, idle_windows, overtime_windows
from services.time_utils import hours, to_min, tomorrow

NEW_DRIVER_SHIFT_MIN = 8 * 60


def spare_buses(station: str) -> list[str]:
    return [b["busId"] for b in data.buses() if b["station"] == station and b["status"] == "spare"]


def _take(windows: list[Window], station: str, start: int, end: int) -> Window | None:
    """Best-fit: the smallest window at `station` covering [start, end]; split what's left."""
    fits = [w for w in windows if w.station == station and w.fits(start, end)]
    if not fits:
        return None
    w = min(fits, key=lambda x: (x.kind != "idle", x.minutes))
    windows.remove(w)
    windows += [Window(w.driver_id, w.station, a, b, w.kind) for a, b in ((w.start, start), (end, w.end)) if b > a]
    return w


def optimize(req: OptimizeRequest) -> OptimizeResponse:
    day = data.resolve_day(req.date, default=tomorrow())
    idle = idle_windows(day)
    windows = idle + (overtime_windows(day) if req.allow_overtime else [])

    working = day.working_duties()
    span = {d["driverId"]: [to_min(d["start"]), to_min(d["end"])] for d in working}
    driving = sum(d["drivingMinutes"] for d in working)

    recs = []
    used_total = 0
    for cand in data.express_candidates()[: req.max_new_routes]:
        rt = express_round_trip(cand)
        trial = list(windows)
        assigned: list[tuple[Window, int, int]] = []
        unstaffed = 0
        for dep in cand["departures"]:
            s = to_min(dep)
            w = _take(trial, cand["from"], s, s + rt)
            if w:
                assigned.append((w, s, s + rt))
            else:
                unstaffed += 1

        new_drivers = math.ceil(unstaffed * rt / NEW_DRIVER_SHIFT_MIN)
        has_bus = bool(spare_buses(cand["from"]))
        feasible = unstaffed == 0 and has_bus
        names = sorted({w.driver_id for w, _, _ in assigned})
        used = sum(e - s for _, s, e in assigned)

        if feasible:
            windows = trial  # commit: later candidates can't reuse these minutes
            used_total += used
            driving += 2 * cand["durationMin"] * len(assigned)
            for w, _, e in assigned:
                span[w.driver_id][1] = max(span[w.driver_id][1], e)  # overtime stretches the duty
            ot = sum(1 for w, _, _ in assigned if w.kind == "overtime")
            reason = f"Covered by idle time of {', '.join(names)}" + (f" ({ot} trip(s) on overtime)" if ot else "")
        else:
            problems = []
            if not has_bus:
                problems.append(f"no spare bus at {cand['from']}")
            if unstaffed:
                problems.append(f"{unstaffed} of {len(cand['departures'])} departures unstaffed")
            reason = "; ".join(problems)
            reason = reason[0].upper() + reason[1:]

        recs.append(RouteRecommendation(
            route=cand["routeId"],
            name=cand["name"],
            idle_hours_used=hours(used),
            new_drivers_required=new_drivers,
            feasible=feasible,
            assigned_drivers=names,
            reason=reason,
        ))

    total_span = sum(e - s for s, e in span.values())
    return OptimizeResponse(
        date=day.date,
        current_utilization=driver_utilization(day),
        optimized_utilization=round(100 * driving / total_span, 1) if total_span else 0.0,
        total_idle_hours_available=hours(sum(w.minutes for w in idle)),
        total_idle_hours_used=hours(used_total),
        new_drivers_required=sum(r.new_drivers_required for r in recs),
        recommendations=recs,
    )
