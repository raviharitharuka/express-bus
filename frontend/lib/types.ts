// Response/request shapes from API_CONTRACT.md.

export type Station =
  | "Central Station"
  | "Airport"
  | "North Station"
  | "South Station"
  | "University";

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

export interface IdleWindow {
  start: string;
  end: string;
}

export interface IdleDriver {
  driverId: string;
  homeStation: Station;
  idleHours: number;
  idleWindows: IdleWindow[];
  recommendedRoute: string;
}

export interface IdleDrivers {
  date: string;
  totalDrivers: number;
  idleDriverCount: number;
  totalIdleHours: number;
  drivers: IdleDriver[];
}

export interface OptimizeRequest {
  date?: string;
  allowOvertime?: boolean;
  maxNewRoutes?: number;
}

export interface RouteRecommendation {
  route: string;
  name: string;
  idleHoursUsed: number;
  newDriversRequired: number;
  feasible: boolean;
}

export interface OptimizeResult {
  date: string;
  currentUtilization: number;
  optimizedUtilization: number;
  totalIdleHoursAvailable: number;
  totalIdleHoursUsed: number;
  newDriversRequired: number;
  recommendations: RouteRecommendation[];
}

export type IncidentType = "BREAKDOWN" | "DRIVER_SICK" | "ROAD_CLOSURE";

export interface EmergencyRequest {
  incidentType: IncidentType;
  busId?: string;
  station: Station;
  time?: string;
}

export interface EmergencyResult {
  incidentId: string;
  incidentType: IncidentType;
  status: "DISPATCHED" | "NO_RESOURCES";
  brokenBus: string;
  replacementBus: string;
  driver: string;
  sourceStation: Station;
  destinationStation: Station;
  distanceKm: number;
  etaMinutes: number;
  timeline: { time: string; step: string }[];
}

export interface LotseResult {
  question: string;
  answer: string;
  confidence: number;
  followUps: string[];
}
