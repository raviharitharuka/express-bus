# AI-Powered Express Bus Resource Optimization Platform

## Hackathon Track 1
### Express Buses Despite a Driver Shortage

**Challenge Provider:** Fraunhofer IIS

**Team Members**
- Tharindu Samarakoon
- Ravihari Gunawadha

---

# Running the Backend

FastAPI backend in `backend/`. The API is described field by field in [API_CONTRACT.md](API_CONTRACT.md).

**Requirements:** Python 3.10+ (tested on 3.14). OR-Tools is installed from `requirements.txt`.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload          # http://localhost:8000  (interactive docs: /docs)
```

Run `uvicorn` from inside `backend/`; the imports are relative to that folder. CORS allows the frontend at `http://localhost:3000`.

**Demo clock (recommended for presentations).** By default "today" and "now" are the real date and time, so at night no driver is on shift. Pin them to the demo dataset:

```bash
DEMO_DATE=2026-10-05 DEMO_TIME=09:15 uvicorn main:app --reload
```

**Tests and helper scripts** (from `backend/`):

```bash
python -m pytest -q                         # rules, endpoints and API contract checks
python scripts/top_idle.py 2026-10-06       # top 10 idle-time pools, per-driver hours
python scripts/generate_data.py             # rebuild data/*.json from the specs in the script
```

## Endpoint examples

Each example works against a server started as above.

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

**`POST /copilot`** — ask in plain English; returns answer text, the matched intent and a structured `data` payload

```bash
curl -X POST http://localhost:8000/copilot \
  -H "Content-Type: application/json" \
  -d '{"question": "Can we launch a new express route tomorrow?"}'
```

Other questions it understands: "Which drivers are idle at the airport?", "What happens if bus B021 breaks down at 09:15?", "Which station needs more buses?", "Are we short of drivers this month?"

**`GET /dashboard`** — KPIs, station status, top recommendation and alerts (default date: today)

```bash
curl http://localhost:8000/dashboard
```

**`GET /health`**

```bash
curl http://localhost:8000/health
```

---

# Executive Summary

Nuremberg has sufficient buses to launch additional express services, but a shortage of drivers limits the city's ability to expand public transportation capacity.

Our proposed solution is an AI-powered optimization platform that identifies hidden driver capacity, optimizes timetables and route assignments, dynamically manages operational disruptions, and predicts future transportation demand.

By combining timetable optimization, workforce planning, fleet management, and predictive analytics, the system enables transport operators to launch additional express services while minimizing the need for additional staff.

---

# Problem Statement

Public transport operators face a significant challenge:

Although enough buses are available to support additional express services, there are not enough drivers to operate them efficiently.

Several operational inefficiencies contribute to this problem:

- Driver idle time between trips
- Uneven shift utilization
- Bus relocation inefficiencies
- Service disruptions due to breakdowns
- Manual scheduling limitations
- Difficulty forecasting future demand

As a result, valuable resources remain underutilized while passenger demand continues to grow.

---

# Project Goal

## Launch Additional Express Routes Using Existing Resources

The primary objective is to maximize utilization of:

- Existing drivers
- Existing buses
- Existing bus stations
- Existing operational schedules

Without:

- Hiring additional drivers
- Purchasing additional buses
- Increasing operational complexity

---

# Solution Overview

The platform consists of four primary AI engines:

### 1. Driver Idle-Time Detection Engine
Identifies unused driver capacity across schedules and stations.

### 2. Schedule Optimization Engine
Generates optimized monthly operational plans.

### 3. Emergency Recovery Engine
Handles breakdowns and operational disruptions automatically.

### 4. Future Prediction Engine
Forecasts passenger demand, driver shortages, and fleet risks.

---

# Solution Architecture

```text
                         Historical Data
                                |
                                v

+-------------+     +----------------------+     +-------------+
| Timetables  |---->|                      |     | Bus Fleet   |
+-------------+     |                      |     +-------------+

+-------------+---->|   AI Optimization    |<----+-------------+
| Driver Data |     |      Engine          |     | Emergencies |
+-------------+     |                      |     +-------------+
                    +----------+-----------+
                               |
          +--------------------+------------------+
          |                    |                  |
          v                    v                  v

   Optimized Schedule   Emergency Recovery   Predictions
```

---

# System Inputs

## Input 1: Monthly Timetable

### Required Fields

- Trip ID
- Route
- Departure Time
- Arrival Time
- Frequency
- Start Station
- End Station

### Sample

```json
{
  "tripId": "T001",
  "route": "R1",
  "departureTime": "06:00",
  "arrivalTime": "06:45",
  "frequency": "30 mins",
  "startStation": "Central Station",
  "endStation": "Airport"
}
```

---

## Input 2: Driver Availability

### Required Fields

- Driver ID
- Driver Location
- Vacation Plans
- Overtime Availability

### Recommended Additional Fields

- License Type
- Years of Experience
- Preferred Routes
- Preferred Stations
- Emergency Availability

### Sample

```json
{
  "driverId": "D001",
  "homeStation": "Central Station",
  "vacationDates": [
    "2026-06-12",
    "2026-06-13"
  ],
  "overtimeAvailable": true,
  "maxShiftHours": 10
}
```

---

## Input 3: Bus Availability

### Required Fields

- Station
- Available Buses
- Maintenance Buses

### Recommended Additional Fields

- Bus Type
- Bus Capacity
- Electric/Diesel
- Age
- Maintenance Due Date

### Sample

```json
{
  "stationName": "Central Station",
  "availableBuses": 20,
  "maintenanceBuses": 2
}
```

---

## Input 4: Emergency Inputs

### Example Events

- Bus Breakdown
- Driver Sick Leave
- Road Closure
- Traffic Accident
- Weather Disruption
- Unexpected Passenger Demand

### Sample

```json
{
  "incidentType": "BREAKDOWN",
  "busId": "B021",
  "location": "Airport Terminal",
  "time": "09:15"
}
```

---

# AI Core Modules

## Module 1: Driver Idle-Time Detection

### Objective

Identify unused driver capacity.

### Example

```text
Driver A

Trip 1
06:00 - 07:00

Idle
07:00 - 09:00

Trip 2
09:00 - 10:00
```

### AI Discovery

```text
Unused Driver Capacity = 2 Hours
```

### Recommendation

```text
Assign Additional Express Route
```

### Output

```json
{
  "driver": "D001",
  "idleHours": 2,
  "recommendedRoutes": [
    "Express E2"
  ]
}
```

---

## Module 2: Express Route Feasibility Engine

### Objective

Determine whether additional express routes can be launched without hiring new drivers.

### Checks

- Driver availability
- Idle hours
- Overtime availability
- Bus availability
- Route demand
- Legal regulations

### Output

```text
Airport Express E5

Feasible: YES

New Drivers Required: 0

Available Driver Capacity:
15 Hours
```

---

## Module 3: Emergency Recovery Engine

### Objective

Automatically recover service during disruptions.

### Scenario

```text
Location:
Airport Station

Bus Pool:
0 Available Buses
```

### AI Recovery Process

#### Step 1
Find nearest station with available buses.

```text
Central Station

Available Buses:
5

Distance:
8 km
```

#### Step 2
Find nearest available driver.

```text
Driver:
D034

Availability:
Until 14:00
```

#### Step 3
Allocate replacement.

```text
Driver D034

Collect Bus B041

Drive to Airport Station
```

#### Step 4
Update system information.

```text
Bus Inventory

Driver Assignment

Timetable

Station Capacity
```

### Output

```json
{
  "replacementBus": "B041",
  "driver": "D034",
  "sourceStation": "Central Station",
  "destinationStation": "Airport Station",
  "estimatedArrival": "15 minutes"
}
```

---

## Module 4: Duty Optimization Engine

### Objective

Generate the most efficient timetable.

### Driver Constraints

- Maximum Shift Hours
- Maximum Driving Hours
- Mandatory Rest Periods
- Vacation Days
- Overtime Permission

### Bus Constraints

- Current Bus Availability
- Maintenance Windows
- Station Location
- Bus Type

### Operational Constraints

- No Overlapping Trips
- Required Service Frequency
- Route Coverage Requirements

### Optimization Objective

#### Maximize

- Passenger Coverage
- Driver Utilization
- Fleet Utilization

#### Minimize

- Idle Driver Hours
- Overtime Cost
- Relocation Distance
- Uncovered Trips

---

## Module 5: Future Prediction Engine

### Objective

Predict future operational requirements.

### Input Data

- Passenger Demand
- Timetables
- Driver Availability
- Breakdowns
- Maintenance Records

### Prediction 1: Demand Forecasting

```text
Airport Route

Fridays

16:00-20:00

Predicted Demand Increase:
30%
```

Recommendation:

```text
Launch Extra Express Route
```

### Prediction 2: Driver Shortage Forecast

```text
Expected Driver Shortage

Date:
24 December

Drivers Missing:
3
```

Recommendation:

```text
Activate Overtime Pool
```

### Prediction 3: Maintenance Risk Prediction

```text
Bus:
B003

Failure Probability:
81%
```

Recommendation:

```text
Schedule Preventive Maintenance
```

---

# AI Dispatcher Copilot

A conversational assistant for transportation managers.

### Example Questions

```text
Can we launch a new express route tomorrow?

Which drivers have unused capacity today?

What happens if Bus B021 breaks down now?

Which station will run out of buses tonight?

What is the best allocation plan for tomorrow?
```

---

# Suggested Technology Stack

## Frontend

- React
- Next.js
- Tailwind CSS
- Mapbox

## Backend

- Python
- FastAPI

## Database

- PostgreSQL
- Redis

## Optimization Engine

- Google OR-Tools

Used for:

- Schedule optimization
- Route assignment
- Driver allocation
- Shift planning

## Machine Learning Models

- Random Forest
- XGBoost

Used for:

- Demand prediction
- Driver shortage prediction
- Maintenance prediction

## Emergency Routing

- Dijkstra Algorithm
- Nearest Neighbor Search

Used for:

- Nearest driver search
- Nearest bus search
- Fastest relocation path

---

# Dashboard Features

## KPI Dashboard

Display:

- Driver Utilization %
- Fleet Utilization %
- Available Drivers
- Available Buses
- Predicted Shortages
- Additional Routes Identified

## Map View

Display:

- Bus Locations
- Available Drivers
- Breakdowns
- Recovery Assignments
- Route Status

## AI Recommendation Panel

```text
Recommendation

Launch Express Route E7

Reason

12 Idle Driver Hours Identified

Confidence

92%
```

---

# Innovation Highlights

## Hidden Capacity Discovery

Find unused driver and fleet capacity automatically.

## Autonomous Breakdown Recovery

Automatically dispatch replacement buses and drivers.

## Express Route Simulator

Simulate potential new express services.

## Future Demand Prediction

Predict operational needs before they occur.

## Fleet Rebalancing

Move buses intelligently between stations.

---

# Hardcoded MVP Dataset

## Stations

- Central Station
- Airport
- North Station
- South Station
- University

## Drivers

```text
D001 - D020
```

## Buses

```text
B001 - B050
```

## Routes

```text
R1 - R10
```

## Schedule

```text
30-Day Monthly Timetable
```

## Emergency Events

- Bus Breakdown
- Driver Sick Leave
- Road Closure

This keeps development manageable during the hackathon.