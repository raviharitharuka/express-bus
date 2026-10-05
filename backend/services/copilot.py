"""Rule-based dispatcher copilot: maps a question to an engine and phrases the result."""

import re

from errors import ApiError
from schemas.copilot import CopilotRequest, CopilotResponse
from schemas.emergency import EmergencyRequest
from schemas.optimize import OptimizeRequest
from services import data
from services.dashboard import worst_shortage
from services.emergency import handle_incident
from services.idle import get_idle_drivers
from services.optimizer import optimize, spare_buses
from services.time_utils import today, tomorrow

EXAMPLES = [
    "Can we launch a new express route tomorrow?",
    "Which drivers have unused capacity today?",
    "What happens if Bus B021 breaks down now?",
    "Which station will run out of buses tonight?",
    "Are we short of drivers this month?",
]


def _date_for(q: str) -> str:
    return (tomorrow() if "tomorrow" in q else today()).isoformat()


def _express(q: str) -> str:
    res = optimize(OptimizeRequest(date=_date_for(q), allow_overtime="overtime" in q))
    ok = [r for r in res.recommendations if r.feasible]
    bad = [r for r in res.recommendations if not r.feasible]
    if not ok:
        return f"No express route can be staffed from idle time on {res.date}. " + "; ".join(
            f"{r.route}: {r.reason}" for r in bad)
    text = (f"Yes. On {res.date} {len(ok)} express route(s) can launch with 0 new drivers: "
            + ", ".join(f"{r.route} ({r.name}, {r.idle_hours_used} h)" for r in ok)
            + f". Driver utilization rises from {res.current_utilization}% to {res.optimized_utilization}%.")
    if bad:
        text += " Not feasible: " + "; ".join(f"{r.route} ({r.reason})" for r in bad) + "."
    return text


def _idle(q: str) -> str:
    res = get_idle_drivers(_date_for(q))
    top = sorted(res.drivers, key=lambda d: -d.idle_hours)[:5]
    return (f"{res.idle_driver_count} of {res.total_drivers} drivers have {res.total_idle_hours} idle hours on {res.date}. "
            "Most capacity: " + ", ".join(f"{d.driver_id} ({d.idle_hours} h at {d.idle_windows[0].station})" for d in top) + ".")


def _breakdown(q: str, bus_id: str) -> str:
    bus = next((b for b in data.buses() if b["busId"] == bus_id), None)
    if not bus:
        return f"Bus {bus_id} does not exist. Buses run from B001 to B050."
    res = handle_incident(EmergencyRequest(incident_type="BREAKDOWN", bus_id=bus_id, station=bus["station"]))
    if res.status != "DISPATCHED":
        return f"If {bus_id} breaks down at {bus['station']} now, no replacement is available: {res.timeline[-1].step}."
    return (f"If {bus_id} breaks down at {res.destination_station}, driver {res.driver} brings {res.replacement_bus} "
            f"from {res.source_station} in about {res.eta_minutes} minutes.")


def _buses(_: str) -> str:
    counts = {s: len(spare_buses(s)) for s in data.station_names()}
    empty = [s for s, n in counts.items() if n == 0]
    ranked = ", ".join(f"{s} {n}" for s, n in sorted(counts.items(), key=lambda x: x[1]))
    lead = f"{' and '.join(empty)} has no spare buses. " if empty else "Every station has at least one spare bus. "
    return lead + f"Spare buses per station: {ranked}."


def _shortage(_: str) -> str:
    day, missing = worst_shortage(today().isoformat())
    if not missing:
        return "No driver shortage is predicted in the 30-day calendar."
    return (f"Worst predicted shortage: {missing} driver(s) missing on {day} due to vacations. "
            "Recommendation: activate the overtime pool for that day.")


INTENTS = [
    (r"\bb\d{3}\b", None),  # breakdown, handled specially
    (r"express|launch|new route|allocation|plan", _express),
    (r"idle|unused|capacity|free driver|available driver", _idle),
    (r"short|vacation|missing", _shortage),
    (r"run out|spare|buses|fleet", _buses),
]


def ask(req: CopilotRequest) -> CopilotResponse:
    q = req.question.lower()
    answer, confidence = None, 90
    for pattern, handler in INTENTS:
        m = re.search(pattern, q)
        if not m:
            continue
        try:
            answer = _breakdown(q, m.group(0).upper()) if handler is None else handler(q)
        except ApiError as e:
            answer, confidence = e.message, 60
        break
    if answer is None:
        answer = ("I can answer questions about express route feasibility, idle drivers, "
                  "bus breakdowns, spare buses per station and driver shortages.")
        confidence = 40
    follow_ups = [e for e in EXAMPLES if e.lower() != q.strip()][:3]
    return CopilotResponse(question=req.question, answer=answer, confidence=confidence, follow_ups=follow_ups)
