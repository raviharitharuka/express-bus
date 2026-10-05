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
import { axisTick, gridStroke, tooltipStyle } from "@/components/chartTheme";

export const FLEET_COLORS = {
  inService: "#6366f1", // indigo-500
  spare: "#10b981", // emerald-500
  maintenance: "#f59e0b", // amber-500
};

function toFleetRows(stations: StationStatus[]) {
  return stations.map((s) => ({
    name: s.name.replace(" Station", ""),
    inService: s.totalBuses - s.availableBuses - s.maintenanceBuses,
    spare: s.availableBuses,
    maintenance: s.maintenanceBuses,
  }));
}

export function StationFleetChart({ stations }: { stations: StationStatus[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={toFleetRows(stations)} margin={{ top: 4, right: 8, left: -16, bottom: 0 }} barSize={32}>
        <CartesianGrid vertical={false} stroke={gridStroke} />
        <XAxis dataKey="name" tickLine={false} axisLine={false} tick={axisTick} />
        <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <Tooltip cursor={{ fill: "#f8fafc" }} contentStyle={tooltipStyle} />
        <Legend itemSorter={null} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
        <Bar dataKey="inService" name="In service" stackId="fleet" fill={FLEET_COLORS.inService} />
        <Bar dataKey="spare" name="Spare" stackId="fleet" fill={FLEET_COLORS.spare} />
        <Bar
          dataKey="maintenance"
          name="Maintenance"
          stackId="fleet"
          fill={FLEET_COLORS.maintenance}
          radius={[4, 4, 0, 0]}
        />
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
