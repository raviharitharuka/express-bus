"""Emergency recovery: find the nearest spare bus and the closest free driver."""

import itertools
import math

from errors import ApiError
from schemas.emergency import EmergencyRequest, EmergencyResponse, TimelineStep
from services import data
from services.idle import Window, idle_windows, overtime_windows
from services.time_utils import now_hhmm, to_hhmm, to_min

DEADHEAD_KMH = 30  # empty bus / driver transfer speed
_incident_ids = itertools.count(1)


def _eta(km: float) -> int:
    return math.ceil(km / DEADHEAD_KMH * 60)


def _nearest_spare_bus(station: str, exclude: str | None) -> tuple[str, str] | None:
    for src in sorted(data.station_names(), key=lambda s: data.distance_km(s, station)):
        spares = [b for b in data.spare_buses(src) if b != exclude]
        if spares:
            return src, spares[0]
    return None


def _free_driver(day: data.Day, t: int, pickup: str, dest: str, exclude: str | None) -> tuple[Window, int] | None:
    """Driver free at time t who can reach `pickup`, then `dest`, before their window ends. Returns (window, km)."""
    best = None
    for w in idle_windows(day) + overtime_windows(day):
        if w.driver_id == exclude or not (w.start <= t < w.end):
            continue
        km = data.distance_km(w.station, pickup) + data.distance_km(pickup, dest)
        if t + _eta(km) > w.end:
            continue
        key = (km, w.kind != "idle", w.driver_id)  # prefer short trips, then idle over overtime
        if best is None or key < best[0]:
            best = (key, w, km)
    return (best[1], best[2]) if best else None


def _no_resources(req, incident_id, dest, broken_bus, steps) -> EmergencyResponse:
    return EmergencyResponse(
        incident_id=incident_id, incident_type=req.incident_type, status="NO_RESOURCES",
        broken_bus=broken_bus, replacement_bus=None, driver=None, source_station=None,
        destination_station=dest, distance_km=None, eta_minutes=None, timeline=steps,
    )


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
    incident_id = f"INC-{next(_incident_ids):04d}"
    steps: list[TimelineStep] = []

    def log(offset: int, text: str):
        steps.append(TimelineStep(time=to_hhmm(t + offset), step=text))

    if req.incident_type == "BREAKDOWN":
        bus_ids = {b["busId"] for b in data.buses()}
        if not req.bus_id:
            raise ApiError(400, "INVALID_REQUEST", "busId is required for BREAKDOWN")
        if req.bus_id not in bus_ids:
            raise ApiError(404, "BUS_NOT_FOUND", f"Bus {req.bus_id} does not exist")
        broken, sick_driver = req.bus_id, None
        log(0, f"Breakdown reported: {broken} at {dest}")

        found = _nearest_spare_bus(dest, exclude=broken)
        if not found:
            log(0, "No spare bus at any station")
            return _no_resources(req, incident_id, dest, broken, steps)
        source, bus = found
        if source == dest:
            log(0, f"Spare bus {bus} available at {dest}")
        else:
            log(0, f"{dest} has 0 spare buses; nearest is {source} "
                   f"({len(data.spare_buses(source))} spare, {data.distance_km(source, dest)} km)")
    else:  # DRIVER_SICK: the bus stays, we need a new driver at the incident station
        drivers = data.drivers()
        if not req.driver_id:
            raise ApiError(400, "INVALID_REQUEST", "driverId is required for DRIVER_SICK")
        if req.driver_id not in drivers:
            raise ApiError(404, "DRIVER_NOT_FOUND", f"Driver {req.driver_id} does not exist")
        duty = next((d for d in data.duties() if d["driverId"] == req.driver_id), None)
        broken, sick_driver = None, req.driver_id
        bus = req.bus_id or (duty["busId"] if duty else None)
        source = dest
        log(0, f"Driver {sick_driver} reported sick at {dest}" + (f"; {bus} is waiting" if bus else ""))

    found = _free_driver(day, t, source, dest, exclude=sick_driver)
    if not found:
        log(1, f"No driver is free at {time}")
        return _no_resources(req, incident_id, dest, broken, steps)
    window, km = found
    driver = window.driver_id
    until = to_hhmm(window.end)
    log(1, f"{'Idle' if window.kind == 'idle' else 'Overtime'} driver {driver} selected "
           f"at {window.station} (free until {until})")

    offset = 1
    if window.station != source:
        transfer = _eta(data.distance_km(window.station, source))
        log(offset + 1, f"{driver} transfers {window.station} -> {source} ({data.distance_km(window.station, source)} km)")
        offset += 1 + transfer
    log(offset + 1, f"{driver} departs {source} with {bus}" if source != dest else f"{driver} takes over {bus}")
    eta = offset + 1 + _eta(data.distance_km(source, dest))
    if source != dest:
        log(eta, f"{bus} arrives at {dest}; {broken} sent to maintenance, inventory updated")
    else:
        log(eta, "Service resumes; duty roster updated")

    return EmergencyResponse(
        incident_id=incident_id,
        incident_type=req.incident_type,
        status="DISPATCHED",
        broken_bus=broken,
        replacement_bus=bus,
        driver=driver,
        source_station=source,
        destination_station=dest,
        distance_km=km,
        eta_minutes=eta,
        timeline=steps,
    )
