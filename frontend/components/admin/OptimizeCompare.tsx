"use client";

import { useSyncExternalStore } from "react";
import { ArrowRight, LoaderCircle, RefreshCw } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";
import { compareStore, plannedExpressTrips, rerunOptimization, serverCompareState } from "./compareStore";

type Better = "higher" | "lower";

const METRICS: { label: string; hint: string; value: (r: OptimizeResult) => number; better: Better; unit?: string }[] = [
  {
    label: "New drivers required",
    hint: "Hires needed across all express candidates",
    value: (r) => r.newDriversRequired,
    better: "lower",
  },
  {
    label: "Express trips per day",
    hint: "Trips in the recommended launch plan",
    value: plannedExpressTrips,
    better: "higher",
  },
  {
    label: "Driver utilization after plan",
    hint: "Driving time ÷ duty span with the plan",
    value: (r) => r.optimizedUtilization,
    better: "higher",
    unit: "%",
  },
];

/** "Re-run optimization" after a driver or bus change, with a before/after summary. */
export function OptimizeCompare() {
  const { pending, running, error, last } = useSyncExternalStore(compareStore.subscribe, compareStore.get, serverCompareState);
  if (pending === 0 && !last && !running && !error) return null;

  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-indigo-900">
          {pending > 0 ? (
            <>
              <span className="font-medium">
                {pending} change{pending === 1 ? "" : "s"}
              </span>{" "}
              since the last optimization. Re-run it to see the effect.
            </>
          ) : running ? (
            "Re-running optimization…"
          ) : (
            <span className="font-medium">Optimization re-run with your changes</span>
          )}
        </p>
        <button
          onClick={rerunOptimization}
          disabled={running || pending === 0}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {running ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
          Re-run optimization
        </button>
      </div>

      {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">Optimization failed: {error}</p>}

      {last && pending === 0 && <Summary before={last.before} after={last.after} />}
    </div>
  );
}

function Summary({ before, after }: { before: OptimizeResult | null; after: OptimizeResult }) {
  const routes = (r: OptimizeResult | null) => (r?.recommended?.length ? r.recommended.join(", ") : "none");
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-indigo-700/80">
            <th className="py-1 pr-4 font-medium">For {after.date}</th>
            <th className="py-1 pr-4 font-medium">Before</th>
            <th className="py-1 pr-4 font-medium">After</th>
            <th className="py-1 font-medium">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-indigo-100">
          {METRICS.map((m) => {
            const a = m.value(after);
            const b = before ? m.value(before) : null;
            return (
              <tr key={m.label}>
                <td className="py-1.5 pr-4 text-slate-700" title={m.hint}>
                  {m.label}
                </td>
                <td className="py-1.5 pr-4 text-slate-500 tabular-nums">{b === null ? "—" : `${b}${m.unit ?? ""}`}</td>
                <td className="py-1.5 pr-4 font-medium text-slate-900 tabular-nums">{`${a}${m.unit ?? ""}`}</td>
                <td className="py-1.5 tabular-nums">{b === null ? "—" : <Delta diff={round(a - b)} better={m.better} unit={m.unit} />}</td>
              </tr>
            );
          })}
          <tr>
            <td className="py-1.5 pr-4 text-slate-700">Recommended routes</td>
            <td className="py-1.5 pr-4 text-slate-500">{before ? routes(before) : "—"}</td>
            <td className="py-1.5 pr-4 font-medium text-slate-900">{routes(after)}</td>
            <td className="py-1.5 text-slate-500">
              {before && routes(before) !== routes(after) ? (
                <span className="inline-flex items-center gap-1">
                  {routes(before)} <ArrowRight className="size-3" /> {routes(after)}
                </span>
              ) : before ? (
                "same"
              ) : (
                "—"
              )}
            </td>
          </tr>
        </tbody>
      </table>
      {!before && <p className="mt-2 text-xs text-slate-500">No earlier result to compare with.</p>}
    </div>
  );
}

const round = (n: number) => Math.round(n * 10) / 10;

function Delta({ diff, better, unit = "" }: { diff: number; better: Better; unit?: string }) {
  if (diff === 0) return <span className="text-slate-500">no change</span>;
  const good = better === "higher" ? diff > 0 : diff < 0;
  return (
    <span className={`font-medium ${good ? "text-emerald-700" : "text-rose-700"}`}>
      {diff > 0 ? "+" : "−"}
      {Math.abs(diff)}
      {unit}
    </span>
  );
}
