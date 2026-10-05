# ExpressBus: Express Buses Despite a Driver Shortage

Hackathon Track 1 · Challenge provider: Fraunhofer IIS

**Team:** Tharindu Samarakoon, Ravihari Gunawadha

ExpressBus is a prototype for a bus operator that has spare buses but not enough drivers. It finds the idle time inside existing driver duties, uses an OR-Tools CP-SAT model to test whether extra express routes can be staffed from that idle time (or with overtime) and how many new drivers they would otherwise need, plans the recovery when a bus breaks down, and shows the results in a FastAPI backend with a Next.js dashboard. It runs on a hand-made synthetic dataset or on real VAG Nürnberg bus trips from the VGN GTFS feed combined with a synthetic driver and bus roster. The original concept, including the parts not built, is in [docs/project_vision.md](docs/project_vision.md).

## What it does

- **Idle-time detection** (`GET /idle-drivers`): per driver, driving hours, idle gaps of 60 min or more with their station, and free capacity up to the max shift.
- **Express route optimization** (`POST /optimize`): a CP-SAT model assigns express round trips to drivers' idle time (or allowed overtime), reports new drivers needed, idle and overtime hours used, utilization before/after and the assignment table, and recommends routes that fit together; 8 s time limit with a cached fallback.
- **Breakdown and sick-driver recovery** (`POST /emergency`): takes the broken bus out of the pool, picks the nearest station with a spare bus and the nearest free driver, and returns the ETA and a timeline (road closures return 501, not implemented).
- **Dashboard** (`GET /dashboard`): driver and fleet utilization, idle drivers, spare buses per station, driver shortages from the vacation calendar, a launch recommendation and rebalancing suggestions.
- **Lotse assistant** (`POST /lotse`, alias `POST /copilot`): keyword matching routes a question to one of the services above and returns text plus the service's data; with an Anthropic API key, Claude classifies the question and phrases the answer from that data, falling back to the keyword rules on any error.
- **Admin** (`/admin/*`): searchable lists of drivers, buses, stations and routes; in-memory overrides (sick leave, vacations, overtime, bus status) that every service picks up; reset; runtime data-source switch.
- **Frontend** (`frontend/`): Overview, Optimization, Emergency Recovery, Ask Lotse and Admin pages; falls back to the mock files in `frontend/public/mock/` when the backend is unreachable.
- **Data scripts** (`backend/scripts/`): synthetic data generator, GTFS filter, GTFS-to-app converter, idle-time report, and an independent solution validator.
- **Tests:** 116 pytest tests covering the rules, every endpoint and the API contract in [API_CONTRACT.md](API_CONTRACT.md).

## Data: what is real and what is synthetic

`DATA_SOURCE` selects the dataset: `synthetic` (default) or `gtfs`. `GET /health` and `GET /admin/status` return a `dataNote` saying which parts are real.

| | `synthetic` | `gtfs` |
|---|---|---|
| Timetable trips (route numbers, departure/arrival times) | Synthetic (one weekday template + 30-day calendar, October 2026) | **Real**: VAG Nürnberg city bus trips from the VGN GTFS feed for Wednesday 2026-07-01 (53 lines, 4,750 trips) |
| Stops / stations | Synthetic (5 stations) | **Real** stop names and coordinates (116 trip terminals) |
| Routes | Synthetic (10 lines) | **Real** line numbers and names; duration and frequency derived from the real trips |
| Driver rosters and duties | Synthetic | Synthetic: the real trips are chained into invented duties (GTFS has no rosters) |
| Drivers (overtime, max shift, vacations) | Synthetic | Synthetic |
| Buses (fleet, depots, spares, capacity) | Synthetic | Synthetic, including a 10 % spare reserve |
| Express route candidates | Synthetic (3) | Synthetic (3, chosen by a script) |
| Distances between stations | Synthetic (straight line × 1.35) | Synthetic (straight line × 1.35, from the real coordinates) |
| Passenger demand | **Not modelled**: there is no demand or ridership data in either dataset | Not modelled |

The GTFS pipeline: `scripts/filter_gtfs.py` cuts the full feed in `data/gtfs/` (not committed) down to `data/filtered/` (committed), and `scripts/build_real_timetable.py` turns that into `backend/data/*_gtfs*.json`. Each GTFS-based file has a `provenance` key listing its real and synthetic parts.

## Quick start

**Requirements:** Python 3.10 or newer (developed and tested with 3.14), Node.js 20.9 or newer (the minimum for Next.js 16; developed with Node 24), and Git.

```bash
git clone https://github.com/raviharitharuka/express-bus.git
cd express-bus
```

**One command** (macOS / Linux / WSL; `run_demo.bat` on Windows):

```bash
./run_demo.sh                    # synthetic data
DATA_SOURCE=gtfs ./run_demo.sh   # real VAG trips, synthetic roster
```

It installs what's missing on the first run, starts the backend on http://localhost:8000 and the frontend on http://localhost:3000, warms up `/optimize`, and prints the URLs. Logs go to `.demo-logs/`.

**Manually**, in two terminals (bash syntax; on Windows use `run_demo.bat`, or `python` instead of `python3` and `set DATA_SOURCE=synthetic` etc. on separate lines before `uvicorn`):

```bash
# backend
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DATA_SOURCE=synthetic DEMO_DATE=2026-10-05 DEMO_TIME=09:15 uvicorn main:app --port 8000
```

```bash
# frontend
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

Run `uvicorn` from inside `backend/`; imports are relative to that folder. CORS allows the frontend at `http://localhost:3000`. `npm install` may print an `allowScripts` warning about `unrs-resolver` and an ESLint deprecation notice; both are harmless and the app runs without them.

**Settings** (environment variables, or `backend/.env` copied from `backend/.env.example`; environment variables win):

| Variable | Value for the demo | Meaning |
|---|---|---|
| `DATA_SOURCE` | `synthetic` (or `gtfs`) | Dataset loaded at startup |
| `DEMO_DATE` | `2026-10-05` for `synthetic`, `2026-07-01` for `gtfs` | "Today". Without it the real date is used, which may be outside the data |
| `DEMO_TIME` | `09:15` | "Now" for emergencies. Without it the real time is used, and at night no driver is on shift |
| `OPTIMIZE_TIME_LIMIT_S` | unset (8 s) | Time budget for one `/optimize` request |
| `ANTHROPIC_API_KEY` | optional | Enables Claude in Lotse; empty = keyword rules only. Never commit a real key |
| `NEXT_PUBLIC_API_BASE_URL` (frontend) | unset (`http://localhost:8000`) | Backend URL, see `frontend/.env.example` |
| `NEXT_PUBLIC_USE_MOCKS` (frontend) | unset (`false`) | `true` = use only `frontend/public/mock/`, no backend |

Before presenting, `POST /admin/reset` (or "Reset all changes" on the Admin page) returns every result to its original value.

**Tests and scripts** (from `backend/`, with the venv activated: `source .venv/bin/activate`):

```bash
python -m pytest -q                         # rules, endpoints and API contract checks
python scripts/top_idle.py 2026-10-06       # top 10 idle-time pools, per-driver hours
python scripts/generate_data.py             # rebuild data/*.json from the specs in the script
python scripts/filter_gtfs.py               # data/gtfs/ (full VGN feed, see below) -> data/filtered/ (VAG buses, one weekday)
python scripts/build_real_timetable.py      # data/filtered/ -> backend/data/*_gtfs*.json (real trips + synthetic roster)
python scripts/validate_solution.py         # check /optimize assignments against every rule, both data sources (PASS/FAIL)
```

**Rebuilding the GTFS data (optional).** The converted GTFS data is already in the repository, so `DATA_SOURCE=gtfs` works without this. To rebuild it from the source feed, download [GTFS.zip](https://www.vgn.de/opendata/GTFS.zip) from [VGN open data](https://www.vgn.de/web-entwickler/open-data/) (about 15 MB; downloading means accepting VGN's terms of use), unzip it into `data/gtfs/` at the repository root (git-ignored), then run `filter_gtfs.py` and `build_real_timetable.py`. A newer feed may contain different dates; `filter_gtfs.py --date YYYYMMDD` picks a specific weekday.

```bash
mkdir -p data/gtfs && unzip GTFS.zip -d data/gtfs     # from the repository root
cd backend && python scripts/filter_gtfs.py && python scripts/build_real_timetable.py
```

## Endpoints

Every field is documented in [API_CONTRACT.md](API_CONTRACT.md); interactive docs at http://localhost:8000/docs. Each example works against a server started as above.

**`GET /idle-drivers`** — driving hours, idle gaps and free capacity per driver (default date: tomorrow)

```bash
curl "http://localhost:8000/idle-drivers?date=2026-10-06"
```

**`POST /optimize`** — test express routes with the CP-SAT model and get a launch recommendation. An empty body tests the 3 built-in candidates (E1–E3); or send your own:

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-10-06", "allowOvertime": true, "candidates": [{"startStation": "Central Station", "endStation": "Airport", "headwayMin": 60, "serviceStart": "09:30", "serviceEnd": "12:30", "tripDurationMin": 20}]}'
```

**`POST /emergency`** — bus breakdown recovery. This **changes the live bus pool**; reset it with `POST /emergency/reset`.

```bash
curl -X POST http://localhost:8000/emergency \
  -H "Content-Type: application/json" \
  -d '{"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport", "time": "09:15"}'

curl -X POST http://localhost:8000/emergency/reset
```

**`POST /lotse`** — ask Lotse, the dispatcher assistant, in plain English; returns answer text, the matched intent, a structured `data` payload and `explainedBy` (`claude` or `rules`). `POST /copilot`, the assistant's earlier name, is an alias.

```bash
curl -X POST http://localhost:8000/lotse \
  -H "Content-Type: application/json" \
  -d '{"question": "Can we launch a new express route tomorrow?"}'
```

Other questions it understands: "Which drivers are idle at the airport?", "What happens if bus B021 breaks down at 09:15?", "Which station needs more buses?", "Are we short of drivers this month?"

**`GET /dashboard`** — KPIs, station status, top recommendation and alerts (default date: today)

```bash
curl http://localhost:8000/dashboard
```

**`GET /health`** — status, `dataSource` and `dataNote`

```bash
curl http://localhost:8000/health
```

### Admin endpoints

Overrides live in memory only (the JSON files are never changed) and immediately affect `/idle-drivers`, `/optimize`, `/emergency` and `/dashboard`.

**`GET /admin/status`** — data source and note, counts, last `/optimize` time, number of active overrides

```bash
curl http://localhost:8000/admin/status
```

**`POST /admin/data-source`** — switch between `synthetic` and `gtfs` at runtime (clears all overrides; `.env` applies again after a restart)

```bash
curl -X POST http://localhost:8000/admin/data-source -H "Content-Type: application/json" -d '{"dataSource": "synthetic"}'
```

**`GET /admin/drivers`**, **`/admin/buses`**, **`/admin/stations`**, **`/admin/routes`** — paginated lists with optional `q` search

```bash
curl "http://localhost:8000/admin/drivers?q=university"
curl "http://localhost:8000/admin/buses?page=2&pageSize=10"
curl "http://localhost:8000/admin/stations?q=north"
curl "http://localhost:8000/admin/routes?q=airport"
```

**`PATCH /admin/drivers/{id}`** — e.g. mark D002 unavailable (sick) until reset; `/optimize` stops using them

```bash
curl -X PATCH http://localhost:8000/admin/drivers/D002 -H "Content-Type: application/json" -d '{"available": false}'
```

**`PATCH /admin/buses/{id}`** — e.g. mark a spare bus broken, or move it (`"station": "Airport"`); `"status": "available"` puts it back

```bash
curl -X PATCH http://localhost:8000/admin/buses/B027 -H "Content-Type: application/json" -d '{"status": "broken"}'
```

**`POST /admin/reset`** — clear every override (admin edits and emergency changes)

```bash
curl -X POST http://localhost:8000/admin/reset
```

## Simplified rules and limitations

This is a prototype. The scheduling rules below are simplified for the demo; **nothing here claims compliance with EU Regulation 561/2006, German working-time law or any collective agreement.** `scripts/validate_solution.py` checks optimizer output against these simplified rules only.

What the optimizer (`backend/services/express_model.py`) models:

- **Driver start location:** a driver can take an express trip only while standing at its start station: in a gap between two of their own trips at that station, or before/after their duty at its first/last stop (the latter only as overtime).
- **Express trips** are full round trips (out, a fixed turnaround at the end station, back), so the driver ends where the next scheduled trip leaves.
- **Max shift:** duty span (first departure to last arrival) ≤ the driver's `maxShiftHours`; new hires 8 h.
- **Breaks:** at most 4.5 h of driving in any rolling 5 h window; layovers count as break time and may be split.
- **Vacation and sick leave:** drivers on vacation that day, or marked unavailable, get no trips; drivers without a duty that day are not called in.
- **Overtime:** only extending the rostered duty span counts as overtime, and only if the driver accepts overtime and the request allows it; idle gaps inside a duty are treated as already paid.
- **Bus availability:** express trips running at the same time ≤ spare buses at the start station.
- **New drivers:** virtual hires at the route's start station, up to 4 per route, used only when existing drivers can't cover a trip.

What it does **not** model:

- **Repositioning:** no empty trips between stations, and no handover buffer: an express trip may leave the minute the driver arrives and return the minute their next trip leaves.
- **Labour rules beyond the above:** no daily or weekly driving-time caps, no rest periods between days, no qualifications or route knowledge.
- **Buses:** no bus types or capacities in the optimizer, no moving spare buses between stations for express service.
- **Demand:** no passenger data; routes are compared on staffing, trips and utilization, not riders.
- **Time:** each dataset covers one representative weekday (GTFS: weekday duties only; trips running past midnight are dropped).
- **Emergency recovery:** ETAs use straight-line distance × 1.35 at a fixed 30 km/h; `ROAD_CLOSURE` returns 501.
- **Forecasts:** "predicted shortages" come from vacation dates in the calendar; there is no prediction model.
- **State:** overrides, emergency changes and the `/optimize` cache live in server memory and are lost on restart; there is no database and no authentication.
- **GTFS mode:** duties, drivers and buses are generated by chaining real trips at the same terminal, so idle time reflects that heuristic, not VAG's real duty plans.

## Roadmap

Not built yet (see [docs/project_vision.md](docs/project_vision.md) for the original ideas):

- Machine-learning prediction of demand, driver shortages and maintenance risk.
- GTFS-Realtime for live vehicle positions and delays.
- Real driver rosters and vehicle schedules from the operator.
- Ticketing or passenger-count data for demand.
- A database instead of JSON files and in-memory state.
- Authentication and roles.
- Maps (the Emergency page shows a schematic placeholder), and road-closure recovery.

## Credits and license

- Challenge provided by Fraunhofer IIS for the hackathon.
- Timetable data: VGN open data ([terms of use](https://www.vgn.de/web-entwickler/open-data/nutzungsbedingungen/)). Source: »VGN – Verkehrsverbund Großraum Nürnberg GmbH«. Filtered to VAG Nürnberg city buses and converted by this project's scripts. VGN's download page names [CC BY 3.0 DE](https://creativecommons.org/licenses/by/3.0/de/), its terms of use [CC BY-SA 3.0 DE](https://creativecommons.org/licenses/by-sa/3.0/de/); this project follows the stricter CC BY-SA.
- Built with FastAPI, Pydantic, Google OR-Tools (CP-SAT), pandas, the Anthropic Python SDK, Next.js, React, Tailwind CSS, Recharts and lucide-react.

**License.** The code and the synthetic data are under the [MIT License](LICENSE). The files derived from VGN data (`data/filtered/` and `backend/data/*_gtfs*.json`) remain under **CC BY-SA 3.0 DE** (attribution: VGN; share-alike applies to anything built from them), not MIT.
