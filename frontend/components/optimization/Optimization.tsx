"use client";

import { useState } from "react";
import { CircleCheck, CircleX, Clock, Gauge, Loader2, Play, TrendingUp, UserPlus, Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { OptimizeResult } from "@/lib/types";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { FEASIBLE_COLOR, INFEASIBLE_COLOR, RouteChart } from "./RouteChart";

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
            description="Run the optimizer to see which express routes can launch from idle driver capacity."
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
  const feasible = recommendations.filter((r) => r.feasible);

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="Current utilization"
          value={`${currentUtilization}%`}
          progress={currentUtilization}
          hint="Driver utilization today"
          icon={Gauge}
          accent="sky"
        />
        <KpiCard
          label="Optimized utilization"
          value={`${optimizedUtilization}%`}
          progress={optimizedUtilization}
          hint="After launching feasible routes"
          icon={Zap}
        />
        <KpiCard
          label="Improvement"
          value={`${gainPts >= 0 ? "+" : ""}${gainPts} pts`}
          hint={`${gainRel >= 0 ? "+" : ""}${gainRel.toFixed(1)}% relative increase`}
          icon={TrendingUp}
          accent="emerald"
        />
        <KpiCard
          label="Idle hours used"
          value={`${result.totalIdleHoursUsed} h`}
          progress={(result.totalIdleHoursUsed / result.totalIdleHoursAvailable) * 100}
          hint={`of ${result.totalIdleHoursAvailable} h available`}
          icon={Clock}
          accent="violet"
        />
        <KpiCard
          label="New drivers required"
          value={result.newDriversRequired}
          hint={`${feasible.length} of ${recommendations.length} routes need none`}
          icon={UserPlus}
          accent="amber"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card title="Express route recommendations" subtitle={`For ${result.date}`} className="lg:col-span-3">
          <div className="-mx-5 overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-y border-slate-100 bg-slate-50 text-left text-xs font-medium whitespace-nowrap text-slate-500">
                  <th className="px-5 py-2.5">Route</th>
                  <th className="px-3 py-2.5 text-right">Idle hours used</th>
                  <th className="px-3 py-2.5 text-right">New drivers</th>
                  <th className="px-5 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recommendations.map((r) => (
                  <tr key={r.route} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-7 min-w-9 items-center justify-center rounded-md bg-indigo-50 px-2 font-mono text-xs font-semibold text-indigo-700">
                          {r.route}
                        </span>
                        <span className="text-slate-700">{r.name}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right text-slate-900 tabular-nums">{r.idleHoursUsed} h</td>
                    <td
                      className={`px-3 py-3 text-right tabular-nums ${
                        r.newDriversRequired > 0 ? "font-medium text-amber-700" : "text-slate-900"
                      }`}
                    >
                      {r.newDriversRequired}
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap">
                      {r.feasible ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200 ring-inset">
                          <CircleCheck className="size-3.5" /> Feasible
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200 ring-inset">
                          <CircleX className="size-3.5" /> Needs drivers
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Idle hours by route" subtitle="Driver capacity each route would absorb" className="lg:col-span-2">
          <RouteChart routes={recommendations} />
          <div className="mt-3 flex justify-center gap-4 text-xs text-slate-600">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: FEASIBLE_COLOR }} /> Feasible
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: INFEASIBLE_COLOR }} /> Needs new drivers
            </span>
          </div>
        </Card>
      </div>
    </>
  );
}

function ResultsSkeleton() {
  const block = "animate-pulse rounded-xl border border-slate-200 bg-white";
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className={`${block} h-32`} />
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className={`${block} h-80 lg:col-span-3`} />
        <div className={`${block} h-80 lg:col-span-2`} />
      </div>
    </>
  );
}
