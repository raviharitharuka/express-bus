"""KPI dashboard: aggregates the other engines into one payload."""

from schemas.dashboard import Alert, DashboardResponse, Kpis, Recommendation, StationStatus
from schemas.optimize import OptimizeRequest
from services import data
from services.fleet import in_service_buses, rebalancing_moves, station_buses
from services.idle import driver_utilization, idle_windows
from services.optimizer import optimize


def worst_shortage(from_date: str) -> tuple[str | None, int]:
    """Calendar day (on/after from_date) with the most duties left without a driver."""
    days = [c for c in data.calendar() if c["date"] >= from_date and c["uncoveredDuties"]]
    if not days:
        return None, 0
    worst = max(days, key=lambda c: len(c["uncoveredDuties"]))
    return worst["date"], len(worst["uncoveredDuties"])


def get_dashboard(date: str | None) -> DashboardResponse:
    day = data.resolve_day(date)
    working = day.working_duties()
    buses = data.buses()
    drivers = data.drivers()
    opt = optimize(OptimizeRequest(date=day.date))
    shortage_day, missing = worst_shortage(day.date)

    fleet = station_buses()
    stations = [
        StationStatus(
            name=f.station,
            total_buses=f.total,
            available_buses=f.spare,
            maintenance_buses=f.maintenance,
            drivers_on_duty=sum(drivers[d["driverId"]]["homeStation"] == f.station for d in working),
        )
        for f in fleet
    ]

    if opt.recommended:
        trips = sum(r.trips_covered for r in opt.recommendations if r.route in opt.recommended)
        recommendation = Recommendation(
            title=f"Launch Express Route{'s' if len(opt.recommended) > 1 else ''} {', '.join(opt.recommended)}",
            reason=(f"{opt.total_idle_hours_used} idle driver hours cover {trips} express trips with 0 new drivers; "
                    f"utilization {opt.current_utilization}% -> {opt.optimized_utilization}%"),
            confidence=92,
        )
    else:
        recommendation = Recommendation(
            title="Hold new express routes",
            reason="Idle capacity does not cover any candidate route today",
            confidence=70,
        )

    alerts = [Alert(level="warning", message=f"{s.name} has 0 spare buses") for s in stations if s.available_buses == 0]
    alerts += [Alert(level="info", message=f"Move {m.buses} spare bus(es) {m.from_station} -> {m.to_station} ({m.distance_km} km)")
               for m in rebalancing_moves(fleet)]
    if missing:
        alerts.append(Alert(level="critical" if missing >= 3 else "warning",
                            message=f"{missing} driver(s) short predicted on {shortage_day}"))
    maint = [b["busId"] for b in buses if b["status"] == "maintenance"]
    if maint:
        alerts.append(Alert(level="info", message=f"{len(maint)} buses in maintenance: {', '.join(maint)}"))

    return DashboardResponse(
        date=day.date,
        kpis=Kpis(
            driver_utilization=driver_utilization(day),
            fleet_utilization=round(100 * in_service_buses(day) / len(buses), 1),
            available_drivers=len({w.driver_id for w in idle_windows(day)}),
            available_buses=sum(f.spare for f in fleet),
            predicted_shortages=missing,
            additional_routes_identified=len(opt.recommended),
        ),
        stations=stations,
        recommendation=recommendation,
        alerts=alerts,
    )
