"""Emergency recovery engine.

BREAKDOWN algorithm:
  1. Take the broken bus out of the pool (status -> maintenance at the incident station).
  2. Walk stations from nearest to farthest (distance matrix) that still have a spare bus.
  3. At each, pick the nearest driver who is free from the incident time until the
     replacement arrives: first drivers on shift (idle gap in their duty), then drivers
     willing to do overtime within their max shift. If nobody can, try the next station.
  4. Dispatch: the bus moves to the incident station and the driver is busy until arrival.

DRIVER_SICK skips steps 1-2: the bus stays, only a driver is needed at the incident station.

Fleet and driver changes are kept in memory (see services/data.py), so a second
incident sees the reduced pool. POST /emergency/reset restores the original data.
"""

import itertools
import math

from errors import ApiError
from schemas.emergency import EmergencyRequest, EmergencyResponse, TimelineStep
from services import data
from services.idle import Window, idle_windows, overtime_windows
from services.time_utils import now_hhmm, to_hhmm, to_min

DEADHEAD_KMH = 30  # empty bus / driver transfer speed
DISPATCH_MIN = 1  # time to pick a driver and notify them
_incident_ids = itertools.count(1)


def _travel_min(a: str, b: str) -> int:
    return math.ceil(data.distance_km(a, b) / DEADHEAD_KMH * 60)


def _stations_with_spares(near: str) -> list[tuple[str, list[str]]]:
    by_distance = sorted(data.station_names(), key=lambda s: (data.distance_km(s, near), s))
    return [(s, spares) for s in by_distance if (spares := data.spare_buses(s))]


def _recovery_minutes(w: Window, pickup: str, dest: str) -> int:
    return DISPATCH_MIN + _travel_min(w.station, pickup) + _travel_min(pickup, dest)


def _nearest_free_driver(day: data.Day, t: int, pickup: str, dest: str, exclude: str | None) -> Window | None:
    """Closest driver to `pickup` who is free from t until the replacement reaches `dest`."""
    candidates = [
        w for w in idle_windows(day) + overtime_windows(day)
        if w.driver_id != exclude
        and data.driver_busy_until(w.driver_id) <= t
        and w.start <= t and t + _recovery_minutes(w, pickup, dest) <= w.end
    ]
    # on-shift drivers first, then overtime; nearest first; driver id breaks ties
    candidates.sort(key=lambda w: (w.kind != "idle", data.distance_km(w.station, pickup), w.driver_id))
    return candidates[0] if candidates else None


def _remaining_trips(bus_id: str, t: int) -> int:
    return sum(1 for legs in data.trips_by_duty().values() for trip in legs
               if trip["busId"] == bus_id and to_min(trip["departureTime"]) >= t)


class _Timeline:
    def __init__(self, t0: int):
        self.t0 = t0
        self.steps: list[TimelineStep] = []

    def add(self, offset: int, text: str) -> None:
        self.steps.append(TimelineStep(time=to_hhmm(self.t0 + offset), step=text))


def handle_incident(req: EmergencyRequest) -> EmergencyResponse:
    if req.incident_type == "ROAD_CLOSURE":
        raise ApiError(501, "NOT_IMPLEMENTED", "ROAD_CLOSURE recovery is not implemented yet")

    dest = data.require_station(req.station)
    time = req.time or now_hhmm()
    try:
        t = to_min(time)
    except ValueError:
        raise ApiError(400, "INVALID_TIME", f"Time '{time}' must be HH:MM")
    day = data.resolve_day(None)
    timeline = _Timeline(t)
    result = dict(
        incident_id=f"INC-{next(_incident_ids):04d}", incident_type=req.incident_type,
        broken_bus=None, replacement_bus=None, driver=None, source_station=None,
        destination_station=dest, distance_km=None, eta_minutes=None, timeline=timeline.steps,
    )

    if req.incident_type == "BREAKDOWN":
        broken = _take_broken_bus_out(req, dest, t, timeline)
        result["broken_bus"] = broken
        stations = _stations_with_spares(dest)
        if not stations:
            timeline.add(0, "No spare bus at any station")
            timeline.add(DISPATCH_MIN, f"Dispatcher action: cancel or merge {broken}'s "
                                       f"{_remaining_trips(broken, t)} remaining trips until a bus is free")
            return EmergencyResponse(status="NO_BUS_AVAILABLE", **result)
        sick = None
    else:  # DRIVER_SICK: the bus stays at the station, only a driver is needed
        sick, bus = _sick_driver_and_bus(req)
        timeline.add(0, f"Driver {sick} reported sick at {dest}" + (f"; {bus} is waiting" if bus else ""))
        stations = [(dest, [bus] if bus else [])]

    for i, (source, spares) in enumerate(stations):
        driver = _nearest_free_driver(day, t, source, dest, exclude=sick)
        if req.incident_type == "BREAKDOWN":
            note = "nearest" if i == 0 else "next nearest"
            timeline.add(0, f"{source} is the {note} station with a spare bus "
                            f"({len(spares)} spare, {data.distance_km(source, dest)} km)")
        if driver:
            return _dispatch(result, timeline, driver, source, spares[0] if spares else None, dest, t)
        timeline.add(0, f"No driver can reach {source} and {dest} in time")

    timeline.add(DISPATCH_MIN, "Dispatcher action: call in a reserve driver")
    return EmergencyResponse(status="NO_DRIVER_AVAILABLE", **result)


def _take_broken_bus_out(req: EmergencyRequest, station: str, t: int, timeline: _Timeline) -> str:
    if not req.bus_id:
        raise ApiError(400, "INVALID_REQUEST", "busId is required for BREAKDOWN")
    bus = next((b for b in data.buses() if b["busId"] == req.bus_id), None)
    if not bus:
        raise ApiError(404, "BUS_NOT_FOUND", f"Bus {req.bus_id} does not exist")
    if bus["status"] == "maintenance":
        raise ApiError(409, "BUS_OUT_OF_SERVICE", f"Bus {req.bus_id} is already out of service")
    data.update_bus(req.bus_id, status="maintenance", station=station)
    timeline.add(0, f"Breakdown reported: {req.bus_id} at {station}")
    timeline.add(0, f"{req.bus_id} removed from the bus pool (maintenance)")
    return req.bus_id


def _sick_driver_and_bus(req: EmergencyRequest) -> tuple[str, str | None]:
    if not req.driver_id:
        raise ApiError(400, "INVALID_REQUEST", "driverId is required for DRIVER_SICK")
    if req.driver_id not in data.drivers():
        raise ApiError(404, "DRIVER_NOT_FOUND", f"Driver {req.driver_id} does not exist")
    duty = next((d for d in data.duties() if d["driverId"] == req.driver_id), None)
    data.mark_driver_busy(req.driver_id, 24 * 60)  # off for the rest of the day
    return req.driver_id, req.bus_id or (duty["busId"] if duty else None)


def _dispatch(result: dict, timeline: _Timeline, w: Window, source: str, bus: str | None,
              dest: str, t: int) -> EmergencyResponse:
    on_shift = "on shift, idle" if w.kind == "idle" else "overtime"
    timeline.add(DISPATCH_MIN, f"Driver {w.driver_id} assigned ({on_shift} at {w.station}, free until {to_hhmm(w.end)})")

    offset = DISPATCH_MIN
    if w.station != source:
        offset += _travel_min(w.station, source)
        timeline.add(offset, f"{w.driver_id} reaches {source} ({data.distance_km(w.station, source)} km)")
    if source != dest:
        timeline.add(offset, f"{w.driver_id} departs {source} with {bus}")
        offset += _travel_min(source, dest)
        timeline.add(offset, f"{bus} arrives at {dest}; service resumes")
    else:
        timeline.add(offset, f"{w.driver_id} takes over {bus} at {dest}; service resumes")

    if bus:
        data.update_bus(bus, status="active", station=dest)
    data.mark_driver_busy(w.driver_id, t + offset)
    timeline.add(offset, "Bus pool, driver roster and station inventory updated")

    return EmergencyResponse(
        status="DISPATCHED",
        **{**result, "replacement_bus": bus, "driver": w.driver_id, "source_station": source,
           "distance_km": data.distance_km(w.station, source) + data.distance_km(source, dest),
           "eta_minutes": offset},
    )
