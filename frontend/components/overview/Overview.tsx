"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bus,
  ChartPie,
  CircleAlert,
  Gauge,
  Info,
  Route,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Alert, Dashboard } from "@/lib/types";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { FleetStatusChart, StationFleetChart } from "./charts";

const TOTAL_DRIVERS = 20;
const TOTAL_BUSES = 50;

function formatDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

const ALERT_STYLES: Record<Alert["level"], { icon: typeof Info; className: string }> = {
  info: { icon: Info, className: "bg-sky-50 text-sky-700 ring-sky-200" },
  warning: { icon: AlertTriangle, className: "bg-amber-50 text-amber-800 ring-amber-200" },
  critical: { icon: CircleAlert, className: "bg-rose-50 text-rose-700 ring-rose-200" },
};

export function Overview() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDashboard().then(setData, (e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorBanner title="Couldn't load the dashboard" message={error} />
      </>
    );
  }

  if (!data) return <OverviewSkeleton />;

  const { kpis, stations, recommendation, alerts } = data;

  return (
    <>
      <PageHeader title="Overview" description={`Operations snapshot for ${formatDate(data.date)}`} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="Driver utilization"
          value={`${kpis.driverUtilization}%`}
          progress={kpis.driverUtilization}
          hint="Share of shift hours driving"
          icon={Gauge}
        />
        <KpiCard
          label="Fleet utilization"
          value={`${kpis.fleetUtilization}%`}
          progress={kpis.fleetUtilization}
          hint={`Buses in service of ${TOTAL_BUSES}`}
          icon={ChartPie}
          accent="sky"
        />
        <KpiCard
          label="Available drivers"
          value={kpis.availableDrivers}
          hint={`With idle capacity, of ${TOTAL_DRIVERS}`}
          icon={UserCheck}
          accent="emerald"
        />
        <KpiCard
          label="Available buses"
          value={kpis.availableBuses}
          hint="Spare and ready to dispatch"
          icon={Bus}
          accent="emerald"
        />
        <KpiCard
          label="New express routes"
          value={kpis.additionalRoutesIdentified}
          hint="Feasible with 0 new drivers"
          icon={Route}
          accent="violet"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card
          title="Fleet by station"
          subtitle="Buses in service, spare and in maintenance"
          className="lg:col-span-2"
        >
          <StationFleetChart stations={stations} />
        </Card>
        <Card title="Fleet status" subtitle="All stations combined">
          <FleetStatusChart stations={stations} />
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 p-5 text-white shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium tracking-wide text-indigo-100 uppercase">
            <Sparkles className="size-4" /> AI recommendation
          </div>
          <h2 className="mt-3 text-lg font-semibold">{recommendation.title}</h2>
          <p className="mt-1 text-sm text-indigo-100">{recommendation.reason}</p>
          <div className="mt-5">
            <div className="flex justify-between text-xs text-indigo-100">
              <span>Confidence</span>
              <span className="font-medium text-white">{recommendation.confidence}%</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/20">
              <div className="h-full rounded-full bg-white" style={{ width: `${recommendation.confidence}%` }} />
            </div>
          </div>
        </section>

        <Card title="Alerts" subtitle={`${alerts.length} active`} className="lg:col-span-2">
          <ul className="space-y-2">
            {alerts.map((alert) => {
              const { icon: Icon, className } = ALERT_STYLES[alert.level];
              return (
                <li
                  key={alert.message}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm ring-1 ring-inset ${className}`}
                >
                  <Icon className="size-4 shrink-0" />
                  {alert.message}
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </>
  );
}

function OverviewSkeleton() {
  const block = "animate-pulse rounded-xl border border-slate-200 bg-white";
  return (
    <>
      <PageHeader title="Overview" description="Loading operations snapshot…" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className={`${block} h-32`} />
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className={`${block} h-80 lg:col-span-2`} />
        <div className={`${block} h-80`} />
      </div>
    </>
  );
}
