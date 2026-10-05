// Response/request shapes from API_CONTRACT.md, mirroring backend/schemas/*.py.

/**
 * Station (stop) name. The synthetic dataset has 5 ("Central Station", "Airport", …);
 * DATA_SOURCE=gtfs uses ~116 real VAG stop names ("Nürnberg Flughafen", …).
 */
export type Station = string;

export type DataSourceName = "synthetic" | "gtfs";

// GET /health
export interface Health {
  status: "ok";
  dataSource: DataSourceName;
  /** What in the active dataset is real and what is synthetic. */
  dataNote: string;
}

/** Error body for every non-2xx response. */
export interface ApiErrorBody {
  error: string;
  message: string;
}

// GET /dashboard

export interface DashboardKpis {
  driverUtilization: number;
  fleetUtilization: number;
  availableDrivers: number;
  availableBuses: number;
  predictedShortages: number;
  additionalRoutesIdentified: number;
}

export interface StationStatus {
  name: Station;
  totalBuses: number;
  availableBuses: number;
  maintenanceBuses: number;
  driversOnDuty: number;
}

export interface Recommendation {
  title: string;
  reason: string;
  confidence: number;
}

export interface Alert {
  level: "info" | "warning" | "critical";
  message: string;
}

export interface Dashboard {
  date: string;
  kpis: DashboardKpis;
  stations: StationStatus[];
  recommendation: Recommendation;
  alerts: Alert[];
}

// GET /idle-drivers

export interface IdleWindow {
  start: string;
  end: string;
  station: Station;
}

export interface IdleDriver {
  driverId: string;
  homeStation: Station;
  dutyStart: string;
  dutyEnd: string;
  drivingHours: number;
  idleHours: number;
  freeCapacityHours: number;
  idleWindows: IdleWindow[];
  recommendedRoute: string | null;
}

export interface IdleDrivers {
  date: string;
  totalDrivers: number;
  workingDrivers: number;
  idleDriverCount: number;
  totalIdleHours: number;
  totalFreeCapacityHours: number;
  drivers: IdleDriver[];
}

// POST /optimize

export interface ExpressCandidate {
  routeId?: string;
  name?: string;
  startStation: Station;
  endStation: Station;
  headwayMin: number;
  serviceStart: string;
  serviceEnd: string;
  tripDurationMin: number;
  turnaroundMin?: number;
}

export interface OptimizeRequest {
  date?: string;
  allowOvertime?: boolean;
  /** 1–5 routes; omit to test the built-in candidates E1–E3. */
  candidates?: ExpressCandidate[];
}

export interface TripAssignment {
  tripId: string;
  departure: string;
  returnsAt: string;
  /** D001–D020, NEW-<route>-<n> for a hire, null if uncovered */
  driver: string | null;
  kind: "idle" | "overtime" | "new-driver" | "uncovered";
}

export interface RouteRecommendation {
  route: string;
  name: string;
  startStation: Station;
  endStation: Station;
  tripsRequested: number;
  tripsCovered: number;
  feasible: boolean;
  newDriversRequired: number;
  idleHoursUsed: number;
  overtimeHoursUsed: number;
  utilizationBefore: number;
  utilizationAfter: number;
  reason: string;
  assignments: TripAssignment[];
}

export interface OptimizeResult {
  date: string;
  allowOvertime: boolean;
  currentUtilization: number;
  optimizedUtilization: number;
  totalIdleHoursAvailable: number;
  totalIdleHoursUsed: number;
  overtimeHoursUsed: number;
  newDriversRequired: number;
  recommended: string[];
  summary: string;
  recommendations: RouteRecommendation[];
}

// POST /emergency

export type IncidentType = "BREAKDOWN" | "DRIVER_SICK" | "ROAD_CLOSURE";

export interface EmergencyRequest {
  incidentType: IncidentType;
  station: Station;
  /** Required for BREAKDOWN */
  busId?: string;
  /** Required for DRIVER_SICK */
  driverId?: string;
  time?: string;
}

interface EmergencyBase {
  incidentId: string;
  incidentType: IncidentType;
  /** null for DRIVER_SICK */
  brokenBus: string | null;
  destinationStation: Station;
  timeline: { time: string; step: string }[];
}

export type EmergencyResult =
  | (EmergencyBase & {
      status: "DISPATCHED";
      replacementBus: string;
      driver: string;
      sourceStation: Station;
      distanceKm: number;
      etaMinutes: number;
    })
  | (EmergencyBase & {
      status: "NO_BUS_AVAILABLE" | "NO_DRIVER_AVAILABLE";
      replacementBus: string | null;
      driver: null;
      sourceStation: null;
      distanceKm: null;
      etaMinutes: null;
    });

// POST /copilot (Lotse)

export type LotseRouteSummary = Omit<RouteRecommendation, "assignments">;

export interface LaunchRouteData {
  date: string;
  recommended: string[];
  currentUtilization: number;
  optimizedUtilization: number;
  routes: LotseRouteSummary[];
}

export interface IdleDriversData {
  date: string;
  station: Station | null;
  drivers: Pick<IdleDriver, "driverId" | "idleHours" | "freeCapacityHours" | "idleWindows" | "recommendedRoute">[];
}

export type BreakdownData = EmergencyResult & { hypothetical: true };

export interface StationBusesData {
  minSparePerStation: number;
  stations: { station: Station; spare: number; active: number; maintenance: number; needsBuses: boolean }[];
  moves: { from: Station; to: Station; buses: number; distanceKm: number }[];
}

export type DriverShortageData =
  | { date: string; driversMissing: number; driversOnVacation: string[]; uncoveredDuties: string[] }
  /** No shortage predicted in the calendar. */
  | { date: null; driversMissing: 0 };

interface LotseBase {
  question: string;
  answer: string;
  /** 90 matched or greeting, 50–60 matched but missing info or an error, 30 unknown */
  confidence: number;
  suggestedQuestions: string[];
}

/** `data` is null for greeting/unknown and when an intent couldn't be answered. */
export type LotseResult = LotseBase &
  (
    | { intent: "launch_route"; data: LaunchRouteData | null }
    | { intent: "idle_drivers"; data: IdleDriversData | null }
    | { intent: "breakdown"; data: BreakdownData | null }
    | { intent: "station_buses"; data: StationBusesData | null }
    | { intent: "driver_shortage"; data: DriverShortageData | null }
    | { intent: "greeting" | "unknown"; data: null }
  );

export type LotseIntent = LotseResult["intent"];

// /admin (API_CONTRACT.md section 6). Every response field is optional: the admin API is new and the
// UI must render whatever subset an older backend or a mock file returns.

export interface AdminCounts {
  stations?: number;
  drivers?: number;
  buses?: number;
  routes?: number;
  trips?: number;
}

// GET /admin/status, POST /admin/data-source, POST /admin/reset
export interface AdminStatus {
  dataSource?: DataSourceName;
  counts?: AdminCounts;
  /** Duration of the last POST /optimize; null if none since startup. */
  lastOptimizeMs?: number | null;
  /** Drivers and buses changed by PATCH or emergencies since the last reset. */
  overridesActive?: number;
}

/** Paginated list from GET /admin/{drivers,buses,stations,routes}. */
export interface AdminPage<T> {
  page?: number;
  pageSize?: number;
  total?: number;
  items?: T[];
}

export interface AdminListQuery {
  page?: number;
  pageSize?: number;
  /** Case-insensitive search in any text or number field. */
  q?: string;
}

export interface AdminDriver {
  driverId?: string;
  homeStation?: Station;
  /** Today's duty; null when off (weekend, vacation, sick). */
  dutyId?: string | null;
  overtimeAvailable?: boolean;
  maxShiftHours?: number;
  vacationDates?: string[];
  /** false = sick leave today. */
  available?: boolean;
  overridden?: boolean;
}

export type BusStatus = "active" | "spare" | "maintenance" | "broken";

export interface AdminBus {
  busId?: string;
  station?: Station;
  status?: BusStatus;
  type?: string;
  capacity?: number;
  overridden?: boolean;
}

export interface AdminStation {
  id?: string;
  name?: Station;
  lat?: number;
  lng?: number;
  totalBuses?: number;
  spareBuses?: number;
  driversBased?: number;
}

export interface AdminRoute {
  routeId?: string;
  name?: string;
  from?: Station;
  to?: Station;
  distanceKm?: number;
  durationMin?: number;
  frequencyMin?: number;
}

// PATCH bodies: only the fields sent change.
export interface DriverPatch {
  vacationDates?: string[];
  overtimeAvailable?: boolean;
  maxShiftHours?: number;
  available?: boolean;
}

export type BusStatusChange = "available" | "maintenance" | "broken";

export interface BusPatch {
  status?: BusStatusChange;
  station?: Station;
}
