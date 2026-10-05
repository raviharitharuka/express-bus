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
  overtimeHoursUsed: number;
  newDriversRequired: number;
  recommended: string[];
  summary: string;
  recommendations: RouteRecommendation[];
}

export type IncidentType = "BREAKDOWN" | "DRIVER_SICK" | "ROAD_CLOSURE";

export interface EmergencyRequest {
  incidentType: IncidentType;
  busId?: string;
  station: Station;
  time?: string;
}

interface EmergencyBase {
  incidentId?: string;
  incidentType?: IncidentType;
  /** null for DRIVER_SICK */
  brokenBus: string | null;
  destinationStation?: Station;
  timeline: { time: string; step: string }[];
}

export type EmergencyResult =
  | (EmergencyBase & {
      status: "DISPATCHED";
      replacementBus: string;
      driver: string;
      sourceStation: Station;
      destinationStation: Station;
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

export interface LotseResult {
  question: string;
  intent: string;
  answer: string;
  confidence: number;
  /** Shape depends on `intent`; null for greeting/unknown. */
  data: Record<string, unknown> | null;
  suggestedQuestions: string[];
}
