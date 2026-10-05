"""Rule-based dispatcher copilot.

Keyword matching picks an intent, the intent calls an existing engine, and the
result comes back as answer text plus a structured `data` payload the UI can
render (tables, map highlights). No LLM involved.
"""

import re
from dataclasses import dataclass
from typing import Callable

from errors import ApiError
from schemas.copilot import CopilotRequest, CopilotResponse
from schemas.emergency import EmergencyRequest
from schemas.optimize import OptimizeRequest
from services import data
from services.dashboard import worst_shortage
from services.emergency import handle_incident
from services.fleet import MIN_SPARE_PER_STATION, rebalancing_moves, station_buses
from services.idle import get_idle_drivers
from services.optimizer import optimize
from services.time_utils import hours, to_min, today, tomorrow

SUGGESTED_QUESTIONS = {
    "launch_route": "Can we launch a new express route tomorrow?",
    "idle_drivers": "Which drivers are idle today?",
    "breakdown": "What happens if bus B021 breaks down at 09:15?",
    "station_buses": "Which station needs more buses?",
    "driver_shortage": "Are we short of drivers this month?",
}


@dataclass
class Reply:
    answer: str
    data: dict | None
    confidence: int = 90


# --- Helpers ----------------------------------------------------------------

def _date_for(q: str) -> str:
    return (tomorrow() if "tomorrow" in q else today()).isoformat()


def _station_in(q: str) -> str | None:
    """'airport', 'central', 'north', 'south', 'university' -> full station name."""
    for name in data.station_names():
        if name.lower().split()[0] in q:
            return name
    return None


def _time_in(q: str) -> str | None:
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", q)
    return f"{int(m[1]):02d}:{m[2]}" if m else None


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else plural or word + 's'}"


# --- Intents ----------------------------------------------------------------

def _launch_route(q: str) -> Reply:
    no_overtime = re.search(r"(no|without) overtime", q) is not None
    res = optimize(OptimizeRequest(date=_date_for(q), allow_overtime=not no_overtime))
    return Reply(
        answer=f"{'Yes' if res.recommended else 'No'}, for {res.date}. {res.summary}",
        data={
            "date": res.date,
            "recommended": res.recommended,
            "currentUtilization": res.current_utilization,
            "optimizedUtilization": res.optimized_utilization,
            "routes": [r.model_dump(by_alias=True, exclude={"assignments"}) for r in res.recommendations],
        },
    )


def _idle_drivers(q: str) -> Reply:
    res = get_idle_drivers(_date_for(q))
    station = _station_in(q)
    idle = [d for d in res.drivers if d.idle_windows]
    if station:
        idle = [d for d in idle if any(w.station == station for w in d.idle_windows)]
    idle.sort(key=lambda d: -d.idle_hours)
    where = f" at {station}" if station else ""
    if not idle:
        return Reply(f"No driver has an idle gap{where} on {res.date}.", {"date": res.date, "drivers": []})
    top = ", ".join(f"{d.driver_id} ({d.idle_hours} h at {d.idle_windows[0].station})" for d in idle[:5])
    return Reply(
        answer=f"{_plural(len(idle), 'driver')} idle{where} on {res.date}, "
               f"{hours(sum(to_min(w.end) - to_min(w.start) for d in idle for w in d.idle_windows))} idle hours "
               f"in total. Most capacity: {top}.",
        data={
            "date": res.date,
            "station": station,
            "drivers": [
                {"driverId": d.driver_id, "idleHours": d.idle_hours, "freeCapacityHours": d.free_capacity_hours,
                 "idleWindows": [w.model_dump(by_alias=True) for w in d.idle_windows],
                 "recommendedRoute": d.recommended_route}
                for d in idle
            ],
        },
    )


def _breakdown(q: str) -> Reply:
    m = re.search(r"\bb\d{3}\b", q)
    station = _station_in(q)
    if m:
        bus_id = m[0].upper()
        bus = next((b for b in data.buses() if b["busId"] == bus_id), None)
        if not bus:
            return Reply(f"Bus {bus_id} does not exist. Buses run from B001 to B050.", None, 60)
    elif station:  # no bus given: take the first bus running from that station
        bus = next((b for b in data.buses() if b["station"] == station and b["status"] == "active"), None)
        if not bus:
            return Reply(f"No bus is running from {station} right now.", None, 60)
    else:
        return Reply("Which bus broke down? Ask e.g. 'What happens if bus B021 breaks down at 09:15?'", None, 50)

    time = _time_in(q)
    when = f"at {time}" if time else "now"
    with data.what_if():  # hypothetical: don't touch the real bus pool
        res = handle_incident(EmergencyRequest(incident_type="BREAKDOWN", bus_id=bus["busId"],
                                               station=station or bus["station"], time=time))
    payload = {"hypothetical": True, **res.model_dump(by_alias=True)}
    if res.status != "DISPATCHED":
        return Reply(f"If {bus['busId']} breaks down at {res.destination_station} {when}, no replacement is "
                     f"available. {res.timeline[-1].step}.", payload)
    where = (f"takes spare {res.replacement_bus} at {res.source_station}"
             if res.source_station == res.destination_station
             else f"brings {res.replacement_bus} from {res.source_station}")
    return Reply(f"If {bus['busId']} breaks down at {res.destination_station} {when}, driver {res.driver} {where}; "
                 f"service resumes in about {_plural(res.eta_minutes, 'minute')}.", payload)


def _station_buses(_: str) -> Reply:
    fleet = station_buses()
    moves = rebalancing_moves(fleet)
    short = [s for s in fleet if s.shortfall]
    if short:
        lead = ", ".join(f"{s.station} ({s.spare} spare)" for s in short)
        answer = f"{lead} {'is' if len(short) == 1 else 'are'} below the {MIN_SPARE_PER_STATION}-spare-bus minimum. "
        answer += ("Suggested: " + "; ".join(f"move {_plural(m.buses, 'bus', 'buses')} from {m.from_station} ({m.distance_km} km)"
                                             f" to {m.to_station}" for m in moves) + ".") if moves \
            else "No other station has spare buses to give."
    else:
        answer = f"Every station has at least {MIN_SPARE_PER_STATION} spare buses."
    return Reply(answer, {
        "minSparePerStation": MIN_SPARE_PER_STATION,
        "stations": [{"station": s.station, "spare": s.spare, "active": s.active, "maintenance": s.maintenance,
                      "needsBuses": s.shortfall > 0} for s in fleet],
        "moves": [{"from": m.from_station, "to": m.to_station, "buses": m.buses, "distanceKm": m.distance_km}
                  for m in moves],
    })


def _driver_shortage(_: str) -> Reply:
    day, missing = worst_shortage(today().isoformat())
    if not missing:
        return Reply("No driver shortage is predicted in the 30-day calendar.", {"date": None, "driversMissing": 0})
    entry = next(c for c in data.calendar() if c["date"] == day)
    return Reply(
        f"Worst predicted shortage: {_plural(missing, 'driver')} missing on {day} "
        f"({', '.join(entry['driversOnVacation'])} on vacation). Recommendation: activate the overtime pool.",
        {"date": day, "driversMissing": missing, "driversOnVacation": entry["driversOnVacation"],
         "uncoveredDuties": entry["uncoveredDuties"]},
    )


# Each intent scores one point per matching keyword pattern; the highest score wins (ties: list order).
INTENTS: list[tuple[str, list[str], Callable[[str], Reply]]] = [
    ("breakdown", [r"break", r"broke", r"fail", r"\bb\d{3}\b"], _breakdown),
    ("station_buses", [r"need\w* more bus", r"run out", r"spare bus", r"rebalanc", r"which station", r"buses"],
     _station_buses),
    ("driver_shortage", [r"short\w* of driver", r"driver shortage", r"vacation", r"missing driver", r"shortage"],
     _driver_shortage),
    ("launch_route", [r"launch", r"new (express )?route", r"express", r"add\w* (a )?route", r"\bplan\b"], _launch_route),
    ("idle_drivers", [r"idle", r"unused", r"capacity", r"free driver", r"available driver", r"drivers? (are|is) free"],
     _idle_drivers),
]


def match_intent(q: str) -> tuple[str, Callable[[str], Reply]] | None:
    scored = [(sum(bool(re.search(p, q)) for p in patterns), -i, name, fn)
              for i, (name, patterns, fn) in enumerate(INTENTS)]
    score, _, name, fn = max(scored)
    return (name, fn) if score else None


def ask(req: CopilotRequest) -> CopilotResponse:
    q = req.question.lower()
    matched = match_intent(q)
    if not matched:
        return CopilotResponse(
            question=req.question, intent="unknown", confidence=30, data=None,
            answer="I didn't catch that. I can check new express routes, idle drivers, "
                   "bus breakdowns, stations that need buses and driver shortages. Try one of these:",
            suggested_questions=list(SUGGESTED_QUESTIONS.values()),
        )
    intent, handler = matched
    try:
        reply = handler(q)
    except ApiError as e:
        reply = Reply(e.message, None, 60)
    return CopilotResponse(
        question=req.question, intent=intent, answer=reply.answer, confidence=reply.confidence, data=reply.data,
        suggested_questions=[s for name, s in SUGGESTED_QUESTIONS.items() if name != intent][:3],
    )
