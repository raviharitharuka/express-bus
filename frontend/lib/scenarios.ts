import type { DataSourceName, EmergencyRequest } from "./types";

/**
 * The breakdown the Emergency page simulates, per backend dataset. Both are an airport
 * breakdown; the bus must be running at that station in the dataset.
 */
export const BREAKDOWN_SCENARIO: Record<DataSourceName, EmergencyRequest> = {
  synthetic: { incidentType: "BREAKDOWN", busId: "B021", station: "Airport" },
  // backend/data/buses_gtfs_synthetic.json: RB0077 is the bus running at Nürnberg Flughafen.
  gtfs: { incidentType: "BREAKDOWN", busId: "RB0077", station: "Nürnberg Flughafen" },
};
