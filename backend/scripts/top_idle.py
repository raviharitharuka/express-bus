"""Print the 10 biggest idle-time pools to sanity check the idle-time engine.

Run from backend/:  python scripts/top_idle.py [YYYY-MM-DD]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import data  # noqa: E402
from services.idle import driver_profiles  # noqa: E402
from services.time_utils import hours, to_hhmm, tomorrow  # noqa: E402


def main():
    day = data.resolve_day(sys.argv[1] if len(sys.argv) > 1 else None, default=tomorrow())
    profiles = driver_profiles(day)
    pools = sorted((w for p in profiles for w in p.windows), key=lambda w: (-w.minutes, w.start))

    print(f"Idle-time pools for {day.date} ({day.day_type}, {len(profiles)} drivers working)\n")
    print(f"{'#':>2}  {'Driver':6}  {'Station':16}  {'Window':13}  {'Hours':>5}")
    for i, w in enumerate(pools[:10], 1):
        print(f"{i:>2}  {w.driver_id:6}  {w.station:16}  {to_hhmm(w.start)}-{to_hhmm(w.end)}  {hours(w.minutes):>5}")

    print(f"\n{'Driver':6}  {'Duty':11}  {'Drive h':>7}  {'Idle h':>6}  {'Free h':>6}")
    for p in sorted(profiles, key=lambda p: -p.free_capacity_minutes):
        print(f"{p.driver_id:6}  {to_hhmm(p.duty_start)}-{to_hhmm(p.duty_end)}  "
              f"{hours(p.driving_minutes):>7}  {hours(p.idle_minutes):>6}  {hours(p.free_capacity_minutes):>6}")

    print(f"\nTotal: {len(pools)} pools, {hours(sum(p.idle_minutes for p in profiles))} idle h, "
          f"{hours(sum(p.free_capacity_minutes for p in profiles))} free capacity h")


if __name__ == "__main__":
    main()
