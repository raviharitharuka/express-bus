"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bus,
  ChartPie,
  CircleAlert,
  CircleCheck,
  Gauge,
  Info,
  RotateCw,
  Route,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Alert, Dashboard } from "@/lib/types";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { BannerButton, ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { CardSkeleton, KpiSkeleton, Skeleton } from "@/components/Skeleton";
import { tone, type Tone } from "@/components/theme";
import { FleetStatusChart, MAX_CHART_STATIONS, StationFleetChart } from "./charts";

/** Alerts shown before "Show all"; real GTFS data produces 100+. */
const ALERTS_PREVIEW = 5;

function formatDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

const ALERT_STYLES: Record<Alert["level"], { icon: typeof Info; tone: Tone }> = {
  info: { icon: Info, tone: "info" },
  warning: { icon: AlertTriangle, tone: "warning" },
  critical: { icon: CircleAlert, tone: "critical" },
};
const ALERT_ORDER: Alert["level"][] = ["critical", "warning", "info"];

export function Overview() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAllAlerts, setShowAllAlerts] = useState(false);

  const fetchDashboard = useCallback(() => {
    api.getDashboard().then(setData, (e: Error) => setError(e.message));
  }, []);

  useEffect(fetchDashboard, [fetchDashboard]);

  function retry() {
    setError(null);
    setData(null);
    fetchDashboard();
  }

  if (error) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorBanner title="Couldn't load the dashboard" message={error}>
          <BannerButton onClick={retry}>
            <RotateCw className="size-3.5" /> Try again
          </BannerButton>
        </ErrorBanner>
      </>
    );
  }

  if (!data) return <OverviewSkeleton />;

  const { kpis, stations, recommendation, alerts } = data;
  const totalBuses = stations.reduce((n, s) => n + s.totalBuses, 0);

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
          hint={`Buses running, of ${totalBuses}`}
          icon={ChartPie}
        />
        <KpiCard
          label="Available drivers"
          value={kpis.availableDrivers}
          hint="Drivers with idle gaps today"
          icon={UserCheck}
          tone="positive"
        />
        <KpiCard
          label="Available buses"
          value={kpis.availableBuses}
          hint="Spare and ready to dispatch"
          icon={Bus}
          tone="positive"
        />
        <KpiCard
          label="New express routes"
          value={kpis.additionalRoutesIdentified}
          hint="Feasible with 0 new drivers"
          icon={Route}
          tone="positive"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card
          title="Fleet by station"
          subtitle={
            stations.length > MAX_CHART_STATIONS
              ? `Largest ${MAX_CHART_STATIONS} of ${stations.length} stations: in service, spare and in maintenance`
              : "Buses in service, spare and in maintenance"
          }
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

        <Card title="Alerts" subtitle={alerts.length ? `${alerts.length} active` : "None active"} className="lg:col-span-2">
          {alerts.length === 0 ? (
            <EmptyState
              compact
              icon={CircleCheck}
              tone="positive"
              title="All clear"
              description="No stations, drivers or buses need attention right now."
            />
          ) : (
            <ul className="space-y-2">
              {[...alerts]
                .sort((a, b) => ALERT_ORDER.indexOf(a.level) - ALERT_ORDER.indexOf(b.level))
                .slice(0, showAllAlerts ? undefined : ALERTS_PREVIEW)
                .map((alert) => {
                  const { icon: Icon, tone: t } = ALERT_STYLES[alert.level];
                  return (
                    <li
                      key={alert.message}
                      className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm ${tone[t].soft}`}
                    >
                      <Icon className="size-4 shrink-0" />
                      {alert.message}
                    </li>
                  );
                })}
            </ul>
          )}
          {alerts.length > ALERTS_PREVIEW && (
            <button
              onClick={() => setShowAllAlerts((v) => !v)}
              className="mt-3 text-sm font-medium text-indigo-600 hover:text-indigo-500"
            >
              {showAllAlerts ? "Show fewer" : `Show all ${alerts.length} alerts`}
            </button>
          )}
        </Card>
      </div>
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading dashboard">
      <PageHeader title="Overview" description="Loading operations snapshot…" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <KpiSkeleton key={i} />
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <CardSkeleton className="lg:col-span-2" />
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="mx-auto mt-8 size-44 rounded-full" />
        </div>
      </div>
    </div>
  );
}
