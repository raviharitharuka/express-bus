"""Admin: inspect and override the data the engines run on (see services/data.py for the overrides layer)."""

import config
from errors import ApiError
from schemas.admin import (AdminStatus, BusItem, BusPatch, Counts, DriverItem, DriverPatch, Page, RouteItem,
                           StationItem)
from services import data

_last_optimize_ms: int | None = None


def record_optimize_ms(ms: int | None) -> None:
    global _last_optimize_ms
    _last_optimize_ms = ms


def status() -> AdminStatus:
    return AdminStatus(
        data_source=config.DATA_SOURCE,
        counts=Counts(
            stations=len(data.stations()),
            drivers=len(data.drivers()),
            buses=len(data.buses()),
            routes=len(data.routes()),
            trips=sum(len(legs) for legs in data.trips_by_duty().values()),
        ),
        last_optimize_ms=_last_optimize_ms,
        overrides_active=len(data.overridden_drivers()) + len(data.overridden_buses()),
    )


def switch_source(name: str) -> AdminStatus:
    data.switch_source(name)
    record_optimize_ms(None)
    return status()


def reset() -> AdminStatus:
    data.reset_live_state()
    record_optimize_ms(None)
    return status()


# --- Lists --------------------------------------------------------------------

def _paginate(items: list, page: int, page_size: int, q: str | None) -> Page:
    """Case-insensitive substring search over every text/number field, then one page."""
    if q:
        needle = q.lower()
        items = [i for i in items
                 if any(needle in str(v).lower() for v in i.model_dump().values() if isinstance(v, (str, int, float)))]
    start = (page - 1) * page_size
    return Page(page=page, page_size=page_size, total=len(items), items=items[start:start + page_size])


def _driver_item(d: dict, duty_of: dict[str, str], overridden: set[str]) -> DriverItem:
    return DriverItem(
        driver_id=d["driverId"], home_station=d["homeStation"], duty_id=duty_of.get(d["driverId"]),
        overtime_available=d["overtimeAvailable"], max_shift_hours=d["maxShiftHours"],
        vacation_dates=d["vacationDates"], available=d["available"], overridden=d["driverId"] in overridden,
    )


def _today_duties() -> dict[str, str]:
    return {d["driverId"]: d["dutyId"] for d in data.resolve_day(None).working_duties()}


def list_drivers(page: int, page_size: int, q: str | None) -> Page:
    duty_of, overridden = _today_duties(), data.overridden_drivers()
    items = [_driver_item(d, duty_of, overridden) for _, d in sorted(data.drivers().items())]
    return _paginate(items, page, page_size, q)


def _bus_item(b: dict, overridden: set[str]) -> BusItem:
    return BusItem(bus_id=b["busId"], station=b["station"], status=b["status"], type=b["type"],
                   capacity=b["capacity"], overridden=b["busId"] in overridden)


def list_buses(page: int, page_size: int, q: str | None) -> Page:
    overridden = data.overridden_buses()
    items = [_bus_item(b, overridden) for b in sorted(data.buses(), key=lambda b: b["busId"])]
    return _paginate(items, page, page_size, q)


def list_stations(page: int, page_size: int, q: str | None) -> Page:
    buses, drivers = data.buses(), data.drivers().values()
    items = [StationItem(
        id=s["id"], name=s["name"], lat=s["lat"], lng=s["lng"],
        total_buses=sum(b["station"] == s["name"] for b in buses),
        spare_buses=sum(b["station"] == s["name"] and b["status"] == "spare" for b in buses),
        drivers_based=sum(d["homeStation"] == s["name"] for d in drivers),
    ) for s in sorted(data.stations(), key=lambda s: s["id"])]
    return _paginate(items, page, page_size, q)


def list_routes(page: int, page_size: int, q: str | None) -> Page:
    items = [RouteItem.model_validate(r) for _, r in sorted(data.routes().items(), key=lambda kv: _route_key(kv[0]))]
    return _paginate(items, page, page_size, q)


def _route_key(route_id: str) -> tuple:
    """R2 before R10; real line numbers 36 before 100."""
    digits = "".join(c for c in route_id if c.isdigit())
    return (route_id.rstrip("0123456789"), int(digits) if digits else 0, route_id)


# --- Patches ------------------------------------------------------------------

def patch_driver(driver_id: str, patch: DriverPatch) -> DriverItem:
    if driver_id not in data.drivers():
        raise ApiError(404, "DRIVER_NOT_FOUND", f"Driver {driver_id} does not exist")
    data.update_driver(driver_id, **patch.model_dump(by_alias=True, exclude_unset=True))
    return _driver_item(data.drivers()[driver_id], _today_duties(), data.overridden_drivers())


def patch_bus(bus_id: str, patch: BusPatch) -> BusItem:
    bus = next((b for b in data.buses() if b["busId"] == bus_id), None)
    if not bus:
        raise ApiError(404, "BUS_NOT_FOUND", f"Bus {bus_id} does not exist")
    fields = {}
    if patch.station is not None:
        fields["station"] = data.require_station(patch.station)
    if patch.status == "available":  # back in service: on a duty today -> active, otherwise spare
        duty_buses = {d["busId"] for d in data.resolve_day(None).working_duties()}
        fields["status"] = "active" if bus_id in duty_buses else "spare"
    elif patch.status:
        fields["status"] = patch.status
    data.update_bus(bus_id, source="admin", **fields)
    return _bus_item(next(b for b in data.buses() if b["busId"] == bus_id), data.overridden_buses())
