"""Cut the VGN GTFS feed down to VAG Nürnberg city buses on one representative weekday.

Run from backend/:
    python scripts/filter_gtfs.py                 # pick the weekday automatically
    python scripts/filter_gtfs.py --date 20261006 # or force a date (YYYYMMDD)

Reads data/gtfs/*.txt (repo root) and writes data/filtered/{routes,trips,stop_times,stops}.csv.

How "VAG Nürnberg" is identified: the VGN feed has a single agency ("VGN") and
routes.agency_id is empty, so there is no VAG agency_id. Instead the first part
of route_id encodes the VGN sub-network: 11 = U-Bahn, 12 = Tram, 13 = Nürnberg
city buses (lines 20-99, route_desc "Stadtbus"), 16 = night buses (mixed
operators). VAG city buses are therefore route_type 3, prefix 13, route_desc
"Stadtbus". Use --prefixes to widen it, e.g. --prefixes 13 16.
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GTFS_DIR = ROOT / "data" / "gtfs"
OUT_DIR = ROOT / "data" / "filtered"

ROUTE_TYPES = {0: "Tram", 1: "Subway/U-Bahn", 2: "Rail", 3: "Bus", 4: "Ferry", 7: "Funicular"}
BUS = 3
VAG_BUS_PREFIXES = ["13"]
VAG_BUS_DESC = "Stadtbus"  # excludes demand-responsive "Linientaxi" under the same prefix
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
REPRESENTATIVE_DAYS = {1, 2, 3}  # Tue-Thu: no Monday/Friday special services


def read(name: str, **kwargs) -> pd.DataFrame:
    # The feed has a UTF-8 BOM; read everything as text so IDs like "0012" stay intact.
    return pd.read_csv(GTFS_DIR / f"{name}.txt", dtype=str, encoding="utf-8-sig", keep_default_na=False, **kwargs)


def ymd(s: str) -> date:
    """GTFS date '20261006' -> date(2026, 10, 6)."""
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def active_services(day: date, calendar: pd.DataFrame, dates: pd.DataFrame) -> set[str]:
    """service_ids running on `day`: weekly pattern in calendar.txt plus/minus calendar_dates.txt exceptions."""
    d = day.strftime("%Y%m%d")
    weekly = calendar[(calendar[WEEKDAYS[day.weekday()]] == "1")
                      & (calendar["start_date"] <= d) & (calendar["end_date"] >= d)]
    services = set(weekly["service_id"])
    on_day = dates[dates["date"] == d]
    services |= set(on_day.loc[on_day["exception_type"] == "1", "service_id"])
    services -= set(on_day.loc[on_day["exception_type"] == "2", "service_id"])
    return services


def pick_weekday(trips: pd.DataFrame, calendar: pd.DataFrame, dates: pd.DataFrame) -> tuple[date, dict[date, int]]:
    """The Tue-Thu with the most trips on the selected routes, i.e. a normal school-term weekday
    (holiday timetables and public holidays have fewer trips). Earliest date wins ties."""
    first, last = ymd(min(calendar["start_date"])), ymd(max(calendar["end_date"]))
    trips_per_service = trips["service_id"].value_counts()
    counts = {}
    day = first
    while day <= last:
        if day.weekday() in REPRESENTATIVE_DAYS:
            services = active_services(day, calendar, dates)
            counts[day] = int(trips_per_service[trips_per_service.index.isin(services)].sum())
        day += timedelta(days=1)
    best = max(counts, key=lambda d: (counts[d], -d.toordinal()))
    return best, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--date", help="service date YYYYMMDD (default: pick a representative Tue-Thu)")
    parser.add_argument("--prefixes", nargs="+", default=VAG_BUS_PREFIXES,
                        help="route_id prefixes treated as VAG buses (default: 13)")
    args = parser.parse_args()

    # (1) Agencies and routes per route_type
    agency = read("agency")
    routes = read("routes")
    print("Agencies:")
    for _, a in agency.iterrows():
        print(f"  {a['agency_id']}: {a['agency_name']} ({a['agency_url']})")
    print("\nRoutes per route_type:")
    for rtype, n in routes["route_type"].astype(int).value_counts().sort_index().items():
        print(f"  {rtype} {ROUTE_TYPES.get(rtype, '?'):14} {n:5}")
    empty_agency = (routes["agency_id"] == "").sum()
    print(f"\nroutes.agency_id is empty for {empty_agency} of {len(routes)} routes; "
          f"VAG buses are taken as route_id prefix {'/'.join(args.prefixes)} with route_desc '{VAG_BUS_DESC}'.")

    # (2) VAG Nürnberg bus routes
    prefix = routes["route_id"].str.split("-").str[0]
    vag = routes[(routes["route_type"].astype(int) == BUS) & prefix.isin(args.prefixes)
                 & (routes["route_desc"] == VAG_BUS_DESC)]
    print(f"VAG bus routes: {len(vag)} route variants, {vag['route_short_name'].nunique()} lines")

    # (3) Representative weekday
    calendar = read("calendar")
    dates = read("calendar_dates")
    all_trips = read("trips")
    vag_trips = all_trips[all_trips["route_id"].isin(vag["route_id"])]
    if args.date:
        day = ymd(args.date)
        print(f"\nService date: {day} ({WEEKDAYS[day.weekday()]}, given with --date)")
    else:
        day, counts = pick_weekday(vag_trips, calendar, dates)
        fewest = min(counts, key=counts.get)
        print(f"\nService date: {day} ({WEEKDAYS[day.weekday()]}): most VAG bus trips of {len(counts)} Tue-Thu dates "
              f"in the feed ({counts[day]} trips; fewest {counts[fewest]} on {fewest})")

    # (4) Trips, stop_times and stops for those routes on that day
    services = active_services(day, calendar, dates)
    trips = vag_trips[vag_trips["service_id"].isin(services)]
    stop_times = read("stop_times")
    stop_times = stop_times[stop_times["trip_id"].isin(trips["trip_id"])]
    stops = read("stops")
    stops = stops[stops["stop_id"].isin(stop_times["stop_id"])]
    routes_out = vag[vag["route_id"].isin(trips["route_id"])]

    # (5) Write small CSVs
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in [("routes", routes_out), ("trips", trips), ("stop_times", stop_times), ("stops", stops)]:
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
    size_kb = sum(f.stat().st_size for f in OUT_DIR.glob("*.csv")) / 1024

    # Summary
    print(f"\nSummary for {day}:")
    print(f"  routes:     {len(routes_out)} variants ({routes_out['route_short_name'].nunique()} lines)")
    print(f"  trips:      {len(trips)}")
    print(f"  stop_times: {len(stop_times)}")
    print(f"  stops:      {len(stops)}")
    print(f"  written to {OUT_DIR.relative_to(ROOT)}/ ({size_kb:.0f} KB)")

    busiest = (trips.merge(routes_out[["route_id", "route_short_name", "route_long_name"]], on="route_id")
               .groupby("route_short_name")
               .agg(trips=("trip_id", "size"), variants=("route_id", "nunique"),
                    name=("route_long_name", lambda s: s.mode().iloc[0]))
               .sort_values(["trips"], ascending=False).head(10))
    print("\n10 busiest lines by trip count (all route_id variants of a line combined):")
    for line, row in busiest.iterrows():
        print(f"  {line:>4}  {row['trips']:4} trips  {row['name']}")

    # block_id check
    filled_all = (all_trips["block_id"] != "").sum()
    filled_day = (trips["block_id"] != "").sum()
    print(f"\nblock_id: filled for {filled_all} of {len(all_trips)} trips in the whole feed "
          f"({100 * filled_all / len(all_trips):.1f}%), {filled_day} of {len(trips)} selected VAG bus trips.")
    if filled_day == 0:
        print("  -> No vehicle blocks for VAG buses: bus and driver duties must be built ourselves (e.g. chain trips).")


if __name__ == "__main__":
    main()
