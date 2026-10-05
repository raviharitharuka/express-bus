"""Fleet status per station and simple rebalancing: which stations need more buses."""

from dataclasses import dataclass

from services import data

MIN_SPARE_PER_STATION = 2  # keep this many spare buses at every station for breakdowns


@dataclass
class StationBuses:
    station: str
    total: int
    active: int
    spare: int
    maintenance: int

    @property
    def shortfall(self) -> int:
        return max(0, MIN_SPARE_PER_STATION - self.spare)


@dataclass
class Move:
    from_station: str
    to_station: str
    buses: int
    distance_km: int


def station_buses() -> list[StationBuses]:
    buses = data.buses()
    out = []
    for name in data.station_names():
        here = [b for b in buses if b["station"] == name]
        out.append(StationBuses(
            station=name,
            total=len(here),
            active=sum(b["status"] == "active" for b in here),
            spare=sum(b["status"] == "spare" for b in here),
            maintenance=sum(b["status"] == "maintenance" for b in here),
        ))
    return out


def rebalancing_moves(stations: list[StationBuses]) -> list[Move]:
    """Cover each station's shortfall from the nearest stations with spares above the minimum."""
    surplus = {s.station: s.spare - MIN_SPARE_PER_STATION for s in stations if s.spare > MIN_SPARE_PER_STATION}
    moves = []
    for s in sorted(stations, key=lambda s: -s.shortfall):
        need = s.shortfall
        for donor in sorted(surplus, key=lambda d: (data.distance_km(d, s.station), d)):
            if need == 0:
                break
            n = min(need, surplus[donor])
            if n:
                moves.append(Move(donor, s.station, n, data.distance_km(donor, s.station)))
                surplus[donor] -= n
                need -= n
    return moves


def in_service_buses(day: data.Day) -> int:
    """Buses running today: today's duty buses that aren't broken, plus emergency replacements."""
    duty_buses = {d["busId"] for d in data.duties()}
    working = {d["busId"] for d in day.working_duties()}
    return sum(
        b["status"] == "active" and (b["busId"] in working or b["busId"] not in duty_buses)
        for b in data.buses()
    )
