"use client";

import { useState } from "react";
import { CircleCheck, CircleX, Clock, Gauge, Loader2, Play, Route, TrendingUp, UserPlus, Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { OptimizeResult } from "@/lib/types";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { CardSkeleton, KpiSkeleton, Skeleton } from "@/components/Skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { chartColor, tone } from "@/components/theme";
import { Headline } from "./Headline";
import { RouteChart } from "./RouteChart";

export function Optimization() {
  const [allowOvertime, setAllowOvertime] = useState(true);
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.optimize({ allowOvertime }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Optimization"
        description="Find idle driver capacity and launch new express routes without hiring."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={allowOvertime}
                onChange={(e) => setAllowOvertime(e.target.checked)}
                className="size-4 rounded border-slate-300 accent-indigo-600"
              />
              Allow overtime
            </label>
            <button
              onClick={run}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              {loading ? "Optimizing…" : result ? "Run again" : "Run optimization"}
            </button>
          </div>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorBanner title="Optimization failed" message={error} />
        </div>
      )}

      {result ? (
        <div className={`transition-opacity ${loading ? "pointer-events-none opacity-50" : ""}`}>
          <Results result={result} />
        </div>
      ) : loading ? (
        <ResultsSkeleton />
      ) : (
        !error && (
          <EmptyState
            icon={Zap}
            title="No optimization run yet"
            description="Test the candidate express lines against today's roster to see which can launch with 0 additional drivers."
            actionLabel="Run optimization"
            onAction={run}
          />
        )
      )}
    </>
  );
}

function Results({ result }: { result: OptimizeResult }) {
  const { currentUtilization, optimizedUtilization, recommendations } = result;
  const gainPts = Math.round((optimizedUtilization - currentUtilization) * 10) / 10;
  const gainRel = currentUtilization > 0 ? (gainPts / currentUtilization) * 100 : 0;
  const needDrivers = recommendations.filter((r) => r.newDriversRequired > 0);

  return (
    <>
      <Headline result={result} />

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="Current utilization"
          value={`${currentUtilization}%`}
          progress={currentUtilization}
          hint="Driver utilization today"
          icon={Gauge}
          tone="neutral"
        />
        <KpiCard
          label="Optimized utilization"
          value={`${optimizedUtilization}%`}
          progress={optimizedUtilization}
          hint="With the recommended lines"
          icon={Zap}
        />
        <KpiCard
          label="Improvement"
          value={`${gainPts >= 0 ? "+" : ""}${gainPts} pts`}
          hint={`${gainRel >= 0 ? "+" : ""}${gainRel.toFixed(1)}% relative increase`}
          icon={TrendingUp}
          tone="positive"
        />
        <KpiCard
          label="Idle hours used"
          value={`${result.totalIdleHoursUsed} h`}
          progress={result.totalIdleHoursAvailable > 0 ? (result.totalIdleHoursUsed / result.totalIdleHoursAvailable) * 100 : 0}
          hint={`of ${result.totalIdleHoursAvailable} h available`}
          icon={Clock}
        />
        <KpiCard
          label="New drivers required"
          value={result.newDriversRequired}
          hint={needDrivers.length ? `Only for ${needDrivers.map((r) => r.route).join(", ")}` : "All candidates fit existing drivers"}
          icon={UserPlus}
          tone={result.newDriversRequired > 0 ? "warning" : "positive"}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Express route candidates" subtitle={`Each line tested on its own for ${result.date}`} className="lg:col-span-2">
          {recommendations.length === 0 ? (
            <EmptyState
              compact
              icon={Route}
              title="No candidate routes"
              description="The optimizer returned no express routes to evaluate for this date."
            />
          ) : (
            <div className="-mx-5 overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-y border-slate-100 bg-slate-50 text-left text-xs font-medium whitespace-nowrap text-slate-500">
                    <th className="px-5 py-2.5">Route</th>
                    <th className="px-3 py-2.5 text-right">Trips</th>
                    <th className="px-3 py-2.5 text-right">Idle hours used</th>
                    <th className="px-3 py-2.5 text-right">New drivers</th>
                    <th className="px-5 py-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recommendations.map((r) => {
                    const recommended = result.recommended.includes(r.route);
                    return (
                      <tr key={r.route} className={recommended ? "bg-emerald-50/40" : "hover:bg-slate-50/60"}>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-3">
                            <span
                              className={`inline-flex h-7 min-w-9 items-center justify-center rounded-md px-2 font-mono text-xs font-semibold ${tone.brand.icon}`}
                            >
                              {r.route}
                            </span>
                            <div className="min-w-0">
                              <p className="text-slate-800">{r.name}</p>
                              <p className="text-xs text-slate-500">{r.reason}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right text-slate-900 tabular-nums">
                          {r.tripsCovered}/{r.tripsRequested}
                        </td>
                        <td className="px-3 py-3 text-right text-slate-900 tabular-nums">{r.idleHoursUsed} h</td>
                        <td
                          className={`px-3 py-3 text-right tabular-nums ${
                            r.newDriversRequired > 0 ? `font-medium ${tone.warning.text}` : "text-slate-900"
                          }`}
                        >
                          {r.newDriversRequired}
                        </td>
                        <td className="px-5 py-3">
                          {recommended ? (
                            <StatusBadge tone="positive" icon={CircleCheck}>
                              Recommended
                            </StatusBadge>
                          ) : r.feasible ? (
                            <StatusBadge tone="brand" icon={CircleCheck}>
                              Feasible alone
                            </StatusBadge>
                          ) : r.newDriversRequired > 0 ? (
                            <StatusBadge tone="warning" icon={CircleX}>
                              Needs drivers
                            </StatusBadge>
                          ) : (
                            <StatusBadge tone="critical" icon={CircleX}>
                              Not feasible
                            </StatusBadge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Idle hours by route" subtitle="Driver capacity each route would absorb">
          <RouteChart routes={recommendations} />
          <div className="mt-3 flex justify-center gap-4 text-xs text-slate-600">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: chartColor.positive }} /> Feasible
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: chartColor.warning }} /> Not feasible
            </span>
          </div>
        </Card>
      </div>
    </>
  );
}

function ResultsSkeleton() {
  return (
    <div aria-busy="true" aria-label="Running optimizer">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="mt-3 h-8 w-2/3" />
        <div className="mt-4 flex gap-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-8 w-64" />
        </div>
      </div>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <KpiSkeleton key={i} />
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <CardSkeleton body="rows" className="lg:col-span-2" />
        <CardSkeleton />
      </div>
    </div>
  );
}
