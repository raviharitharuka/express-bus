"use client";

import { useState } from "react";
import { BusFront, CircleCheck, Clock, Loader2, RotateCcw, Siren, TriangleAlert, UserRound, Wrench } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { BREAKDOWN_SCENARIO } from "@/lib/scenarios";
import type { EmergencyResult } from "@/lib/types";
import { Card } from "@/components/Card";
import { useBackendHealth } from "@/components/DataSource";
import { EmptyState } from "@/components/EmptyState";
import { BannerButton, ErrorBanner } from "@/components/ErrorBanner";
import { KpiCard } from "@/components/KpiCard";
import { PageHeader } from "@/components/PageHeader";
import { CardSkeleton, KpiSkeleton, Skeleton } from "@/components/Skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { RecoveryMap } from "./RecoveryMap";

export function Emergency() {
  // The scenario depends on the backend's dataset (synthetic B021 vs a real-data bus); wait for it.
  const health = useBackendHealth();
  const scenario = BREAKDOWN_SCENARIO[health?.dataSource ?? "synthetic"];
  const [result, setResult] = useState<EmergencyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  async function run(action: () => Promise<EmergencyResult | null>) {
    setLoading(true);
    setError(null);
    try {
      setResult(await action());
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }

  const simulate = () => run(() => api.reportEmergency(scenario));
  // The backend keeps broken buses in maintenance, so the same breakdown can't be reported twice.
  const resetAndSimulate = () =>
    run(async () => {
      await api.resetEmergency();
      return api.reportEmergency(scenario);
    });
  const reset = () =>
    run(async () => {
      await api.resetEmergency();
      return null;
    });
  const busAlreadyOut = error instanceof ApiError && error.code === "BUS_OUT_OF_SERVICE";

  return (
    <>
      <PageHeader
        title="Emergency Recovery"
        description="Report incidents and dispatch replacement buses and drivers automatically."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {result && (
              <button
                onClick={reset}
                disabled={loading}
                title="Undo all breakdowns and dispatches on the backend"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-70"
              >
                <RotateCcw className="size-4" /> Reset demo
              </button>
            )}
            <button
              onClick={simulate}
              disabled={loading || health === undefined}
              className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-rose-500 focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Siren className="size-4" />}
              {loading ? "Dispatching…" : `Simulate breakdown of Bus ${scenario.busId}`}
            </button>
          </div>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorBanner
            title={busAlreadyOut ? `Bus ${scenario.busId} is already in maintenance` : "Recovery plan failed"}
            message={
              busAlreadyOut
                ? "The backend keeps simulated breakdowns until it is reset. Reset the demo to run the scenario again."
                : error.message
            }
          >
            {busAlreadyOut ? (
              <BannerButton onClick={resetAndSimulate}>
                <RotateCcw className="size-3.5" /> Reset demo and simulate again
              </BannerButton>
            ) : (
              <BannerButton onClick={simulate}>
                <RotateCcw className="size-3.5" /> Try again
              </BannerButton>
            )}
          </ErrorBanner>
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
            tone="critical"
            icon={Siren}
            title="No active incident"
            description={`Simulate a breakdown of Bus ${scenario.busId} at ${scenario.station} to see the automatic recovery plan.`}
            actionLabel="Simulate breakdown"
            onAction={simulate}
          />
        )
      )}
    </>
  );
}

function Results({ result }: { result: EmergencyResult }) {
  const dispatched = result.status === "DISPATCHED";
  const lastStep = result.timeline.length - 1;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm shadow-sm">
        <span className="font-mono font-medium text-slate-900">{result.incidentId}</span>
        <span className="text-slate-300">•</span>
        <span className="text-slate-600 capitalize">{result.incidentType.replace("_", " ").toLowerCase()}</span>
        <span className="text-slate-300">•</span>
        <span className="text-slate-600">{result.destinationStation}</span>
        <span className="ml-auto">
          {dispatched ? (
            <StatusBadge tone="positive" icon={CircleCheck}>
              Dispatched
            </StatusBadge>
          ) : (
            <StatusBadge tone="critical" icon={TriangleAlert}>
              {result.status === "NO_BUS_AVAILABLE" ? "No bus available" : "No driver available"}
            </StatusBadge>
          )}
        </span>
      </div>

      {dispatched && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Broken bus"
            value={result.brokenBus ?? "—"}
            hint={`Out of service at ${result.destinationStation}`}
            icon={Wrench}
            tone="critical"
          />
          <KpiCard
            label="Replacement bus"
            value={result.replacementBus}
            hint={`From ${result.sourceStation}`}
            icon={BusFront}
            tone="positive"
          />
          <KpiCard
            label="Driver"
            value={result.driver}
            hint="Idle driver reassigned"
            icon={UserRound}
          />
          <KpiCard
            label="ETA"
            value={`${result.etaMinutes} min`}
            hint={`${result.distanceKm} km to ${result.destinationStation}`}
            icon={Clock}
          />
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card title="Recovery timeline" subtitle="Steps taken by the recovery engine" className="lg:col-span-2">
          <ol>
            {result.timeline.map((t, i) => (
              <li key={i} className="relative flex gap-4 pb-5 last:pb-0">
                {i < lastStep && <span className="absolute top-6 bottom-0 left-[11px] w-px bg-slate-200" />}
                <span
                  className={`relative mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full ring-4 ring-white ${
                    i === lastStep && dispatched ? "bg-emerald-500 text-white" : "bg-indigo-50 text-indigo-600"
                  }`}
                >
                  {i === lastStep && dispatched ? (
                    <CircleCheck className="size-3.5" />
                  ) : (
                    <span className="text-[11px] font-semibold">{i + 1}</span>
                  )}
                </span>
                <div className="min-w-0">
                  <p className="font-mono text-xs text-slate-500">{t.time}</p>
                  <p className="mt-0.5 text-sm text-slate-800">{t.step}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>

        {dispatched && (
          <Card
            title="Recovery route"
            subtitle={`${result.replacementBus} from ${result.sourceStation} to ${result.destinationStation}`}
            className="lg:col-span-3"
          >
            <RecoveryMap
              source={result.sourceStation}
              destination={result.destinationStation}
              distanceKm={result.distanceKm}
            />
          </Card>
        )}
      </div>
    </>
  );
}

function ResultsSkeleton() {
  return (
    <div aria-busy="true" aria-label="Building recovery plan">
      <div className="mb-6 flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="ml-auto h-5 w-24 rounded-full" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <KpiSkeleton key={i} />
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <CardSkeleton body="rows" className="lg:col-span-2" />
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="mt-2 h-3 w-56" />
          <Skeleton className="mt-6 h-72 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
}
