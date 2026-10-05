# API Contract

Shared contract between the FastAPI backend (`backend/`) and the Next.js frontend (`frontend/`).

- **Base URL (dev):** `http://localhost:8000`
- **Format:** JSON, `Content-Type: application/json`
- **Field naming:** `camelCase`
- **Times:** `"HH:MM"` (24h, local). **Dates:** `"YYYY-MM-DD"`. **Percentages:** numbers `0–100`.
- **Mocks:** every endpoint has a matching file in `frontend/public/mock/`, served by Next.js at `/mock/<name>.json`. The frontend can switch between mock and live with one base-URL flag.

## MVP data scale

| Entity   | Values                                                                 |
|----------|------------------------------------------------------------------------|
| Stations | `Central Station`, `Airport`, `North Station`, `South Station`, `University` |
| Drivers  | `D001` – `D020`                                                        |
| Buses    | `B001` – `B050`                                                        |
| Routes   | Regular `R1` – `R10`; new express routes proposed as `E1`, `E2`, …     |

## Errors (all endpoints)

```json
{ "error": "BUS_NOT_FOUND", "message": "Bus B099 does not exist" }
```

HTTP `400` for bad input, `404` for unknown IDs, `500` for server errors.

---

## 1. `GET /idle-drivers`

Drivers with unused capacity (idle gaps between trips) on a given day.

**Query params**

| Param  | Type   | Required | Default  |
|--------|--------|----------|----------|
| `date` | string | no       | tomorrow |

**Response `200`** — mock: `idle-drivers.json`

```json
{
  "date": "2026-10-06",
  "totalDrivers": 20,
  "idleDriverCount": 8,
  "totalIdleHours": 22,
  "drivers": [
    {
      "driverId": "D007",
      "homeStation": "Central Station",
      "idleHours": 4,
      "idleWindows": [
        { "start": "08:30", "end": "10:30" },
        { "start": "13:00", "end": "15:00" }
      ],
      "recommendedRoute": "E1"
    }
  ]
}
```

| Field                         | Type     | Notes                                  |
|-------------------------------|----------|----------------------------------------|
| `totalIdleHours`              | number   | Sum of `drivers[].idleHours`           |
| `drivers[].idleWindows`       | array    | Gaps ≥ 2h between scheduled trips      |
| `drivers[].recommendedRoute`  | string   | Express route this capacity could feed |

---

## 2. `POST /optimize`

Runs the schedule optimizer and returns which express routes can be launched from idle capacity.

**Request**

```json
{
  "date": "2026-10-06",
  "allowOvertime": false,
  "maxNewRoutes": 4
}
```

All fields optional; defaults shown.

**Response `200`** — mock: `optimize.json`

```json
{
  "date": "2026-10-06",
  "currentUtilization": 74,
  "optimizedUtilization": 86,
  "totalIdleHoursAvailable": 22,
  "totalIdleHoursUsed": 20,
  "newDriversRequired": 1,
  "recommendations": [
    { "route": "E1", "name": "Central Station - Airport Express",     "idleHoursUsed": 9,   "newDriversRequired": 0, "feasible": true },
    { "route": "E2", "name": "University - Central Station Express",  "idleHoursUsed": 6.5, "newDriversRequired": 0, "feasible": true },
    { "route": "E3", "name": "North Station - South Station Express", "idleHoursUsed": 4.5, "newDriversRequired": 0, "feasible": true },
    { "route": "E4", "name": "North Station - Airport Express",       "idleHoursUsed": 2,   "newDriversRequired": 1, "feasible": false }
  ]
}
```

| Field                                  | Type    | Notes                                                        |
|----------------------------------------|---------|--------------------------------------------------------------|
| `currentUtilization`                   | number  | Driver utilization % before optimization                     |
| `optimizedUtilization`                 | number  | Driver utilization % after launching feasible routes         |
| `totalIdleHoursUsed`                   | number  | Idle hours consumed by **feasible** routes only              |
| `newDriversRequired`                   | integer | Total across all recommendations                             |
| `recommendations[].idleHoursUsed`      | number  | Idle driver hours the route would consume                    |
| `recommendations[].newDriversRequired` | integer | Extra drivers needed beyond idle capacity                    |
| `recommendations[].feasible`           | boolean | `true` only if `newDriversRequired == 0` and buses available |

---

## 3. `POST /emergency`

Reports an incident and returns the automatic recovery plan.

**Request**

```json
{
  "incidentType": "BREAKDOWN",
  "busId": "B021",
  "station": "Airport",
  "time": "09:15"
}
```

| Field          | Type   | Required | Notes                                              |
|----------------|--------|----------|----------------------------------------------------|
| `incidentType` | enum   | yes      | `BREAKDOWN` \| `DRIVER_SICK` \| `ROAD_CLOSURE`     |
| `busId`        | string | for `BREAKDOWN` | `B001`–`B050`                               |
| `station`      | string | yes      | One of the 5 stations                              |
| `time`         | string | no       | Defaults to now                                    |

**Response `200`** — mock: `emergency.json`

```json
{
  "incidentId": "INC-0042",
  "incidentType": "BREAKDOWN",
  "status": "DISPATCHED",
  "brokenBus": "B021",
  "replacementBus": "B041",
  "driver": "D007",
  "sourceStation": "Central Station",
  "destinationStation": "Airport",
  "distanceKm": 8,
  "etaMinutes": 15,
  "timeline": [
    { "time": "09:15", "step": "Breakdown reported: B021 at Airport" },
    { "time": "09:15", "step": "Airport has 0 spare buses; nearest pool is Central Station (5 available, 8 km)" },
    { "time": "09:16", "step": "Idle driver D007 selected at Central Station (free until 10:30)" },
    { "time": "09:17", "step": "D007 assigned to collect B041 and drive to Airport" },
    { "time": "09:32", "step": "B041 arrives at Airport; timetable and station inventory updated" }
  ]
}
```

| Field        | Type    | Notes                                         |
|--------------|---------|-----------------------------------------------|
| `status`     | enum    | `DISPATCHED` \| `NO_RESOURCES`                |
| `etaMinutes` | integer | Minutes until replacement reaches destination |
| `timeline`   | array   | 3–6 short steps, chronological                |

---

## 4. `POST /copilot`

Natural-language Q&A for dispatchers.

**Request**

```json
{ "question": "Can we launch a new express route tomorrow?" }
```

**Response `200`** — mock: `copilot.json`

```json
{
  "question": "Can we launch a new express route tomorrow?",
  "answer": "Yes. 8 drivers have 22 idle hours tomorrow. E1 (Central Station - Airport), E2 (University - Central Station) and E3 (North Station - South Station) can launch with 0 new drivers. E4 would need 1 extra driver.",
  "confidence": 92,
  "followUps": [
    "Which drivers have unused capacity today?",
    "What happens if Bus B021 breaks down now?",
    "Which station will run out of buses tonight?"
  ]
}
```

| Field        | Type     | Notes                         |
|--------------|----------|-------------------------------|
| `confidence` | number   | 0–100                         |
| `followUps`  | string[] | Suggested next questions (0–3)|

---

## 5. `GET /dashboard`

Everything the KPI dashboard needs in one call.

**Query params:** `date` (optional, default today)

**Response `200`** — mock: `dashboard.json`

```json
{
  "date": "2026-10-06",
  "kpis": {
    "driverUtilization": 74,
    "fleetUtilization": 68,
    "availableDrivers": 8,
    "availableBuses": 12,
    "predictedShortages": 3,
    "additionalRoutesIdentified": 3
  },
  "stations": [
    { "name": "Central Station", "totalBuses": 14, "availableBuses": 5, "maintenanceBuses": 2, "driversOnDuty": 6 }
  ],
  "recommendation": {
    "title": "Launch Express Route E1",
    "reason": "9 idle driver hours identified on Central Station - Airport",
    "confidence": 92
  },
  "alerts": [
    { "level": "warning", "message": "Airport has 0 spare buses" }
  ]
}
```

| Field                         | Type    | Notes                                                       |
|-------------------------------|---------|-------------------------------------------------------------|
| `kpis.fleetUtilization`       | number  | Buses in service / 50                                       |
| `kpis.predictedShortages`     | integer | Drivers missing on the next predicted shortage day          |
| `stations[]`                  | array   | Always 5 entries; `totalBuses` sums to 50, `driversOnDuty` to 20 |
| `stations[].availableBuses`   | integer | Spare buses ready to dispatch (not in service, not in maintenance) |
| `alerts[].level`              | enum    | `info` \| `warning` \| `critical`                           |

---

## Mock data consistency

The mock files tell one coherent story so the demo hangs together:

- 8 idle drivers × 22 idle hours → `idle-drivers.json`
- 20 of those hours fill E1/E2/E3 (0 new drivers); E4 needs 1 driver → `optimize.json`
- Driver utilization 74% → 86% (20h ÷ 160 shift-hours ≈ +12.5 pts)
- Airport has 0 spare buses → B021 breakdown is covered by B041 from Central Station, driven by idle driver D007 → `emergency.json`
- Fleet: 34 in service + 12 spare + 4 maintenance = 50 buses → `dashboard.json`
