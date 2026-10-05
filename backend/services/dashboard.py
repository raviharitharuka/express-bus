"""KPI dashboard: aggregates the other engines into one payload."""

from schemas.dashboard import Alert, DashboardResponse, Kpis, Recommendation, StationStatus
from schemas.optimize import OptimizeRequest
from services import data
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
    in_service = {d["busId"] for d in working}
    opt = optimize(OptimizeRequest(date=day.date))
    feasible = [r for r in opt.recommendations if r.feasible]
    shortage_day, missing = worst_shortage(day.date)

    stations = []
    for name in data.station_names():
        here = [b for b in buses if b["station"] == name]
        stations.append(StationStatus(
            name=name,
            total_buses=len(here),
            available_buses=sum(b["status"] == "spare" for b in here),
            maintenance_buses=sum(b["status"] == "maintenance" for b in here),
            drivers_on_duty=sum(drivers[d["driverId"]]["homeStation"] == name for d in working),
        ))

    if feasible:
        best = max(feasible, key=lambda r: r.idle_hours_used)
        recommendation = Recommendation(
            title=f"Launch Express Route {best.route}",
            reason=f"{best.idle_hours_used} idle driver hours on {best.name} ({', '.join(best.assigned_drivers)})",
            confidence=92,
        )
    else:
        recommendation = Recommendation(
            title="Hold new express routes",
            reason="Idle capacity does not cover any candidate route today",
            confidence=70,
        )

    alerts = [Alert(level="warning", message=f"{s.name} has 0 spare buses") for s in stations if s.available_buses == 0]
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
            fleet_utilization=round(100 * len(in_service) / len(buses), 1),
            available_drivers=len({w.driver_id for w in idle_windows(day)}),
            available_buses=sum(b["status"] == "spare" for b in buses),
            predicted_shortages=missing,
            additional_routes_identified=len(feasible),
        ),
        stations=stations,
        recommendation=recommendation,
        alerts=alerts,
    )
