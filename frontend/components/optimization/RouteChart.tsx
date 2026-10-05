"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RouteRecommendation } from "@/lib/types";
import { axisTick, axisTickMuted, chartColor, cursorFill, gridStroke, tooltipStyle } from "@/components/theme";

export function RouteChart({ routes }: { routes: RouteRecommendation[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={routes} margin={{ top: 4, right: 8, left: -16, bottom: 0 }} barSize={40}>
        <CartesianGrid vertical={false} stroke={gridStroke} />
        <XAxis dataKey="route" tickLine={false} axisLine={false} tick={axisTick} />
        <YAxis tickLine={false} axisLine={false} tick={axisTickMuted} unit="h" />
        <Tooltip
          cursor={{ fill: cursorFill }}
          contentStyle={tooltipStyle}
          labelFormatter={(_, payload) => payload?.[0]?.payload.name ?? ""}
          formatter={(value) => [`${value} h`, "Idle hours used"]}
        />
        <Bar dataKey="idleHoursUsed" radius={[4, 4, 0, 0]}>
          {routes.map((r) => (
            <Cell key={r.route} fill={r.feasible ? chartColor.positive : chartColor.warning} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
