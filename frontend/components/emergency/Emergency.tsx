"use client";

import { useState } from "react";
import { BusFront, CircleCheck, Clock, Loader2, Siren, TriangleAlert, UserRound, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import type { EmergencyRequest, EmergencyResult } from "@/lib/types";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { KpiCard } from "@/components/KpiCard";
import { PageHeader } from "@/components/PageHeader";
import { RecoveryMap } from "./RecoveryMap";

const SCENARIO: EmergencyRequest = { incidentType: "BREAKDOWN", busId: "B021", station: "Airport" };

export function Emergency() {
  const [result, setResult] = useState<EmergencyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function simulate() {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.reportEmergency(SCENARIO));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Emergency Recovery"
        description="Report incidents and dispatch replacement buses and drivers automatically."
        actions={
          <button
            onClick={simulate}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-rose-500 focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Siren className="size-4" />}
            {loading ? "Dispatching…" : `Simulate breakdown of Bus ${SCENARIO.busId}`}
          </button>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorBanner title="Recovery plan failed" message={error} />
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
            icon={Siren}
            title="No active incident"
            description={`Simulate a breakdown of Bus ${SCENARIO.busId} at ${SCENARIO.station} to see the automatic recovery plan.`}
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
        {dispatched ? (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200 ring-inset">
            <CircleCheck className="size-3.5" /> Dispatched
          </span>
        ) : (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-700 ring-1 ring-rose-200 ring-inset">
            <TriangleAlert className="size-3.5" /> No resources available
          </span>
        )}
      </div>

      {dispatched && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Broken bus"
            value={result.brokenBus}
            hint={`Out of service at ${result.destinationStation}`}
            icon={Wrench}
            accent="rose"
          />
          <KpiCard
            label="Replacement bus"
            value={result.replacementBus}
            hint={`From ${result.sourceStation}`}
            icon={BusFront}
            accent="emerald"
          />
          <KpiCard
            label="Driver"
            value={result.driver}
            hint="Idle driver reassigned"
            icon={UserRound}
            accent="violet"
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
  const block = "animate-pulse rounded-xl border border-slate-200 bg-white";
  return (
    <>
      <div className={`${block} mb-6 h-12`} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className={`${block} h-32`} />
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className={`${block} h-96 lg:col-span-2`} />
        <div className={`${block} h-96 lg:col-span-3`} />
      </div>
    </>
  );
}
