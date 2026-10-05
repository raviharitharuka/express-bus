"""CP-SAT model: staff express trips with the existing drivers.

Express trips are extra tasks. Each task is given to at most one driver, and
never overlaps that driver's existing trips or other express tasks.

Objective (lexicographic via weights):
    1. maximize covered express trips
    2. minimize new drivers needed
    3. minimize overtime minutes
    4. tie-break: prefer existing drivers over a new hire for individual trips

SIMPLIFIED RULES (demo scope, not legal advice):
- An express task is a full round trip from the start station: out, turnaround
  at the end station, back. A driver can only take it while standing at the
  start station: in a gap between two of their trips there, or right before /
  after their duty when the start station is their home station. No empty
  repositioning trips between stations.
- Max shift: duty span (first departure to last arrival) <= maxShiftHours.
  No daily driving-time cap or rest period between days.
- Break rule: at most 4.5 h of driving in any rolling 5 h window, i.e. >= 30 min
  of breaks per 5 h. Layovers count as break time and may be split. This stands
  in for EU 561/2006 and the German urban line-service rules. It's checked
  every 5 minutes.
- Overtime = any extension of the rostered duty span. Idle gaps inside the duty
  are already paid, so using them is not overtime. Overtime is only possible if
  the driver has overtimeAvailable and the request allows overtime.
- Vacation: drivers on vacation that day are excluded. Drivers without a duty
  that day (e.g. weekend) are not called in.
- New drivers are virtual hires based at the route's start station: no
  existing trips, 8 h max shift, same break rule, at most 4 per route.
- Buses: express trips running at the same time <= spare buses at the start
  station. No bus types, no relocation from other stations.
"""

from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from services import data
from services.time_utils import to_min

MAX_DRIVING_IN_WINDOW_MIN = 270  # 4.5 h ...
BREAK_WINDOW_MIN = 300  # ... in any rolling 5 h
BREAK_CHECK_STEP_MIN = 5
NEW_DRIVER_MAX_SHIFT_MIN = 8 * 60
MAX_NEW_DRIVERS_PER_ROUTE = 4
DAY_END_MIN = 24 * 60

W_COVERED = 1_000_000  # one covered trip beats any number of hires/overtime
W_NEW_DRIVER = 10_000  # one hire beats any realistic amount of overtime minutes
W_NEW_DRIVER_TRIP = 1  # tie-break: among equal plans, give trips to existing drivers


@dataclass
class Task:
    """One express round trip."""

    task_id: str
    route_id: str
    station: str  # start station: the driver must be here before and after
    start: int  # minutes since midnight
    end: int
    driving: list[tuple[int, int]]  # out leg and back leg

    @property
    def minutes(self) -> int:
        return self.end - self.start

    @property
    def driving_minutes(self) -> int:
        return sum(e - s for s, e in self.driving)


@dataclass
class Slot:
    station: str
    start: int
    end: int
    kind: str  # idle (inside the duty) | overtime (before/after the duty)


@dataclass
class DriverDay:
    driver_id: str
    duty_start: int
    duty_end: int
    max_shift: int  # minutes
    overtime_ok: bool
    driving: list[tuple[int, int]]  # existing trips
    slots: list[Slot]

    @property
    def driving_minutes(self) -> int:
        return sum(e - s for s, e in self.driving)


@dataclass
class Assignment:
    task: Task
    driver_id: str | None
    kind: str  # idle | overtime | new-driver | uncovered


@dataclass
class Solution:
    status: str
    assignments: list[Assignment]
    new_drivers: int
    idle_minutes_used: int
    overtime_minutes: int
    utilization_before: float
    utilization_after: float
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def covered(self) -> int:
        return sum(a.kind != "uncovered" for a in self.assignments)


# --- Inputs -----------------------------------------------------------------

def build_tasks(cand: dict) -> list[Task]:
    dur, turn = cand["tripDurationMin"], cand["turnaroundMin"]
    tasks = []
    for i, dep in enumerate(data.express_departures(cand), 1):
        out_end = dep + dur
        back_start = out_end + turn
        tasks.append(Task(
            task_id=f"{cand['routeId']}-{i}",
            route_id=cand["routeId"],
            station=cand["startStation"],
            start=dep,
            end=back_start + dur,
            driving=[(dep, out_end), (back_start, back_start + dur)],
        ))
    return tasks


def build_driver_days(day: data.Day, allow_overtime: bool) -> list[DriverDay]:
    trips = data.trips_by_duty()
    drivers = data.drivers()
    out = []
    for duty in day.working_duties():
        drv = drivers[duty["driverId"]]
        legs = trips[duty["dutyId"]]
        overtime_ok = allow_overtime and drv["overtimeAvailable"]
        start, end = to_min(legs[0]["departureTime"]), to_min(legs[-1]["arrivalTime"])

        slots = [
            Slot(a["endStation"], to_min(a["arrivalTime"]), to_min(b["departureTime"]), "idle")
            for a, b in zip(legs, legs[1:])
            if a["endStation"] == b["startStation"]
        ]
        if overtime_ok:
            slots.append(Slot(legs[0]["startStation"], 0, start, "overtime"))
            slots.append(Slot(legs[-1]["endStation"], end, DAY_END_MIN, "overtime"))

        out.append(DriverDay(
            driver_id=drv["driverId"],
            duty_start=start,
            duty_end=end,
            max_shift=round(drv["maxShiftHours"] * 60),  # whole minutes for CP-SAT
            overtime_ok=overtime_ok,
            driving=[(to_min(t["departureTime"]), to_min(t["arrivalTime"])) for t in legs],
            slots=slots,
        ))
    return out


def _overlap(intervals: list[tuple[int, int]], lo: int, hi: int) -> int:
    return sum(max(0, min(e, hi) - max(s, lo)) for s, e in intervals)


def _utilization(driving: int, span: int) -> float:
    return round(100 * driving / span, 1) if span else 0.0


# --- Model ------------------------------------------------------------------

def solve(tasks: list[Task], drivers: list[DriverDay], spare_buses: dict[str, int], time_limit_s: float) -> Solution:
    """Solution.status is the CP-SAT status name; anything but OPTIMAL means the solve was cut short."""
    m = cp_model.CpModel()
    x: dict[tuple[int, str], cp_model.IntVar] = {}  # (task index, worker) -> assigned?
    slot_kind: dict[tuple[int, str], str] = {}

    # Which existing driver can take which task (right station, inside a slot)?
    for ti, t in enumerate(tasks):
        for d in drivers:
            slot = next((s for s in d.slots if s.station == t.station and s.start <= t.start and t.end <= s.end), None)
            if slot:
                x[ti, d.driver_id] = m.new_bool_var(f"x_{t.task_id}_{d.driver_id}")
                slot_kind[ti, d.driver_id] = slot.kind

    # Virtual new hires per route, used in order (symmetry breaking).
    new_used: dict[str, cp_model.IntVar] = {}
    for route_id in dict.fromkeys(t.route_id for t in tasks):
        route_tasks = [ti for ti, t in enumerate(tasks) if t.route_id == route_id]
        prev = None
        for k in range(min(MAX_NEW_DRIVERS_PER_ROUTE, len(route_tasks))):
            worker = f"NEW-{route_id}-{k + 1}"
            used = new_used[worker] = m.new_bool_var(f"used_{worker}")
            for ti in route_tasks:
                x[ti, worker] = m.new_bool_var(f"x_{tasks[ti].task_id}_{worker}")
                m.add_implication(x[ti, worker], used)
            if prev is not None:
                m.add(prev >= used)
            prev = used

    # Each task at most once; `covered` links to the bus capacity.
    covered = []
    for ti, t in enumerate(tasks):
        c = m.new_bool_var(f"covered_{t.task_id}")
        m.add(sum(v for (i, _), v in x.items() if i == ti) == c)
        covered.append(c)

    for station in {t.station for t in tasks}:
        ivs = [m.new_optional_fixed_size_interval_var(t.start, t.minutes, covered[ti], f"bus_{t.task_id}")
               for ti, t in enumerate(tasks) if t.station == station]
        m.add_cumulative(ivs, [1] * len(ivs), spare_buses.get(station, 0))

    # Per worker: no overlaps, max shift, breaks, overtime.
    by_id = {d.driver_id: d for d in drivers}
    overtime_terms = []
    for worker in dict.fromkeys(w for _, w in x):
        mine = [(ti, v) for (ti, w), v in x.items() if w == worker]
        m.add_no_overlap([m.new_optional_fixed_size_interval_var(tasks[ti].start, tasks[ti].minutes, v, f"iv_{worker}_{ti}")
                          for ti, v in mine])

        d = by_id.get(worker)
        if d:  # existing driver: span covers the rostered duty plus any express tasks
            s = m.new_int_var(0, d.duty_start, f"start_{worker}")
            e = m.new_int_var(d.duty_end, DAY_END_MIN, f"end_{worker}")
            m.add(e - s <= d.max_shift)
            if d.overtime_ok:
                overtime_terms.append(e - s - (d.duty_end - d.duty_start))
            else:
                m.add(s == d.duty_start)
                m.add(e == d.duty_end)
            base_driving = d.driving
        else:  # new hire
            s = m.new_int_var(0, DAY_END_MIN, f"start_{worker}")
            e = m.new_int_var(0, DAY_END_MIN, f"end_{worker}")
            m.add(e >= s)
            m.add(e - s <= NEW_DRIVER_MAX_SHIFT_MIN)
            base_driving = []
        for ti, v in mine:
            m.add(s <= tasks[ti].start).only_enforce_if(v)
            m.add(e >= tasks[ti].end).only_enforce_if(v)

        # Break rule, only for windows an express task could touch.
        lo = min(tasks[ti].start for ti, _ in mine) - BREAK_WINDOW_MIN
        hi = max(tasks[ti].end for ti, _ in mine)
        for w in range(lo - lo % BREAK_CHECK_STEP_MIN, hi, BREAK_CHECK_STEP_MIN):
            terms = [(o, v) for ti, v in mine if (o := _overlap(tasks[ti].driving, w, w + BREAK_WINDOW_MIN))]
            if terms:
                base = _overlap(base_driving, w, w + BREAK_WINDOW_MIN)
                m.add(base + sum(o * v for o, v in terms) <= MAX_DRIVING_IN_WINDOW_MIN)

    new_driver_trips = [v for (_, w), v in x.items() if w.startswith("NEW-")]
    m.maximize(W_COVERED * sum(covered) - W_NEW_DRIVER * sum(new_used.values()) - sum(overtime_terms)
               - W_NEW_DRIVER_TRIP * sum(new_driver_trips))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1  # single thread: same input, same answer (models are tiny)
    status = solver.solve(m)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return _extract(tasks, drivers, x, slot_kind, solver if ok else None, solver.status_name(status))


def _extract(tasks, drivers, x, slot_kind, solver, status) -> Solution:
    """Read the assignment back and compute the reported numbers from it."""
    assignments = []
    for ti, t in enumerate(tasks):
        worker = next((w for (i, w), v in x.items() if i == ti and solver and solver.value(v)), None)
        if worker is None:
            kind = "uncovered"
        elif worker.startswith("NEW-"):
            kind = "new-driver"
        else:
            kind = slot_kind[ti, worker]
        assignments.append(Assignment(t, worker, kind))

    spans = {d.driver_id: (d.duty_start, d.duty_end) for d in drivers}
    for a in assignments:
        if a.driver_id:
            s, e = spans.get(a.driver_id, (a.task.start, a.task.end))
            spans[a.driver_id] = (min(s, a.task.start), max(e, a.task.end))

    base_driving = sum(d.driving_minutes for d in drivers)
    base_span = sum(d.duty_end - d.duty_start for d in drivers)
    express_driving = sum(a.task.driving_minutes for a in assignments if a.driver_id)
    return Solution(
        status=status,
        assignments=assignments,
        new_drivers=len({a.driver_id for a in assignments if a.kind == "new-driver"}),
        idle_minutes_used=sum(a.task.minutes for a in assignments if a.kind == "idle"),
        overtime_minutes=sum((e - s) - (d.duty_end - d.duty_start)
                             for d in drivers for s, e in [spans[d.driver_id]]),
        utilization_before=_utilization(base_driving, base_span),
        utilization_after=_utilization(base_driving + express_driving, sum(e - s for s, e in spans.values())),
        spans=spans,
    )
