import { BusFront, MapPin } from "lucide-react";
import type { Station } from "@/lib/types";
import { chartColor } from "@/components/theme";

// Schematic positions (% of the map box) for the synthetic dataset, roughly following Nuremberg's layout.
// Placeholder until the Mapbox view lands.
const SCHEMATIC: Record<string, { x: number; y: number }> = {
  Airport: { x: 72, y: 18 },
  "North Station": { x: 38, y: 26 },
  University: { x: 18, y: 58 },
  "Central Station": { x: 52, y: 60 },
  "South Station": { x: 64, y: 86 },
};

export function RecoveryMap({
  source,
  destination,
  distanceKm,
}: {
  source: Station;
  destination: Station;
  distanceKm: number;
}) {
  // Real-data (GTFS) stops aren't on the schematic: show just source and destination, side by side.
  const onSchematic = source in SCHEMATIC && destination in SCHEMATIC;
  const STATIONS = onSchematic
    ? SCHEMATIC
    : { [source]: { x: 22, y: 45 }, [destination]: { x: 78, y: 45 } };
  const from = STATIONS[source];
  const to = STATIONS[destination];
  const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };

  return (
    <div className="relative h-80 overflow-hidden rounded-lg border border-slate-200 bg-slate-50 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:16px_16px]">
      <svg className="absolute inset-0 size-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        <line
          x1={from.x}
          y1={from.y}
          x2={to.x}
          y2={to.y}
          stroke={chartColor.brand}
          strokeWidth={3}
          strokeDasharray="6 5"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      {Object.keys(STATIONS).map((name) => {
        const { x, y } = STATIONS[name];
        const role = name === source ? "source" : name === destination ? "destination" : null;
        return (
          // Anchored on the marker's centre (not marker + label) so a wrapped label doesn't shift it.
          <div
            key={name}
            className={`absolute flex -translate-x-1/2 flex-col items-center ${role ? "-translate-y-4" : "-translate-y-1.5"}`}
            style={{ left: `${x}%`, top: `${y}%` }}
          >
            {role ? (
              <span
                className={`flex size-8 items-center justify-center rounded-full text-white shadow-md ring-4 ${
                  role === "source" ? "bg-indigo-600 ring-indigo-200" : "bg-rose-600 ring-rose-200"
                }`}
              >
                <MapPin className="size-4" />
              </span>
            ) : (
              <span className="size-3 rounded-full border-2 border-white bg-slate-400 shadow" />
            )}
            <span
              className={`mt-1.5 max-w-40 rounded px-1.5 py-0.5 text-center text-xs ${
                role ? "bg-white font-medium text-slate-900 shadow-sm" : "text-slate-500"
              }`}
            >
              {name}
            </span>
          </div>
        );
      })}

      <div
        className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1 rounded-full bg-white px-2 py-1 text-xs font-medium text-indigo-700 shadow-md ring-1 ring-indigo-100"
        style={{ left: `${mid.x}%`, top: `${mid.y}%` }}
      >
        <BusFront className="size-3.5" /> {distanceKm} km
      </div>

      <div className="absolute bottom-3 left-3 flex gap-3 rounded-md bg-white/90 px-2.5 py-1.5 text-xs text-slate-600 shadow-sm">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-indigo-600" /> Source
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-rose-600" /> Incident
        </span>
      </div>
      <span className="absolute top-3 right-3 text-[11px] text-slate-400">Schematic · live map coming soon</span>
    </div>
  );
}
