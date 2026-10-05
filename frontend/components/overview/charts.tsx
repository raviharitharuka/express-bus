"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { StationStatus } from "@/lib/types";
import { axisTick, axisTickMuted, chartColor, cursorFill, gridStroke, tooltipStyle } from "@/components/theme";

// In service = brand, spare = available (positive), maintenance = needs attention (warning).
export const FLEET_COLORS = {
  inService: chartColor.brand,
  spare: chartColor.positive,
  maintenance: chartColor.warning,
};

/** Above this many stations (real GTFS data has ~116) the chart shows the largest ones only. */
export const MAX_CHART_STATIONS = 12;

export function largestStations(stations: StationStatus[]) {
  return stations.length <= MAX_CHART_STATIONS
    ? stations
    : [...stations].sort((a, b) => b.totalBuses - a.totalBuses).slice(0, MAX_CHART_STATIONS);
}

/** Axis label: "Central Station" -> "Central", "Nürnberg Plärrer" -> "Plärrer". */
function shortName(name: string) {
  const short = name.replace(/^Nürnb(?:erg|\.),?\s+/, "").replace(/ Station$/, "");
  return short.length > 22 ? `${short.slice(0, 21)}…` : short;
}

function toFleetRows(stations: StationStatus[]) {
  return stations.map((s) => ({
    name: shortName(s.name),
    fullName: s.name,
    inService: s.totalBuses - s.availableBuses - s.maintenanceBuses,
    spare: s.availableBuses,
    maintenance: s.maintenanceBuses,
  }));
}

export function StationFleetChart({ stations }: { stations: StationStatus[] }) {
  const rows = toFleetRows(largestStations(stations));
  const bars = [
    <Bar key="in" dataKey="inService" name="In service" stackId="fleet" fill={FLEET_COLORS.inService} />,
    <Bar key="spare" dataKey="spare" name="Spare" stackId="fleet" fill={FLEET_COLORS.spare} />,
  ];
  const tooltip = (
    <Tooltip
      cursor={{ fill: cursorFill }}
      contentStyle={tooltipStyle}
      labelFormatter={(_, payload) => payload?.[0]?.payload.fullName ?? ""}
    />
  );
  const legend = <Legend itemSorter={null} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />;

  // Few stations (synthetic data): columns. Many (GTFS stop names): horizontal bars with room for long names.
  if (stations.length <= 8) {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={{ top: 4, right: 8, left: -16, bottom: 0 }} barSize={32}>
          <CartesianGrid vertical={false} stroke={gridStroke} />
          <XAxis dataKey="name" tickLine={false} axisLine={false} tick={axisTick} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={axisTickMuted} />
          {tooltip}
          {legend}
          {bars}
          <Bar dataKey="maintenance" name="Maintenance" stackId="fleet" fill={FLEET_COLORS.maintenance} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={rows.length * 24 + 60}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 12, left: 0, bottom: 0 }} barSize={14}>
        <CartesianGrid horizontal={false} stroke={gridStroke} />
        <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={axisTickMuted} />
        <YAxis type="category" dataKey="name" width={170} tickLine={false} axisLine={false} tick={axisTick} />
        {tooltip}
        {legend}
        {bars}
        <Bar dataKey="maintenance" name="Maintenance" stackId="fleet" fill={FLEET_COLORS.maintenance} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function FleetStatusChart({ stations }: { stations: StationStatus[] }) {
  const rows = toFleetRows(stations);
  const sum = (key: "inService" | "spare" | "maintenance") => rows.reduce((n, r) => n + r[key], 0);
  const data = [
    { name: "In service", value: sum("inService"), color: FLEET_COLORS.inService },
    { name: "Spare", value: sum("spare"), color: FLEET_COLORS.spare },
    { name: "Maintenance", value: sum("maintenance"), color: FLEET_COLORS.maintenance },
  ];
  const total = data.reduce((n, d) => n + d.value, 0);

  return (
    <div>
      <div className="relative">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Tooltip contentStyle={tooltipStyle} />
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={62}
              outerRadius={88}
              paddingAngle={2}
              stroke="none"
            >
              {data.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold text-slate-900 tabular-nums">{total}</span>
          <span className="text-xs text-slate-500">buses</span>
        </div>
      </div>
      <ul className="mt-4 space-y-2">
        {data.map((d) => (
          <li key={d.name} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-slate-600">
              <span className="size-2.5 rounded-full" style={{ background: d.color }} />
              {d.name}
            </span>
            <span className="font-medium text-slate-900 tabular-nums">{d.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
