"use client";

import { useCallback, useEffect, useState } from "react";
import { Database, PencilLine, RotateCcw, RotateCw, Timer } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminStatus, DataSourceName } from "@/lib/types";
import { Card } from "@/components/Card";
import { useBackendHealth, useDataSource } from "@/components/DataSource";
import { BannerButton, ErrorBanner } from "@/components/ErrorBanner";
import { KpiCard } from "@/components/KpiCard";
import { KpiSkeleton, Skeleton } from "@/components/Skeleton";
import { ConfirmDialog } from "./ui";

const SOURCE_LABEL: Record<DataSourceName, string> = { synthetic: "Synthetic demo data", gtfs: "Real GTFS trips" };
const COUNT_LABELS: [keyof NonNullable<AdminStatus["counts"]>, string][] = [
  ["stations", "Stations"],
  ["drivers", "Drivers"],
  ["buses", "Buses"],
  ["routes", "Routes"],
  ["trips", "Trips"],
];

type Pending = { kind: "switch"; to: DataSourceName } | { kind: "reset" } | null;

export function StatusTab() {
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const health = useBackendHealth();
  const source = useDataSource();
  const readOnly = source?.kind === "mock";

  const load = useCallback(() => {
    api.getAdminStatus().then(
      (s) => {
        setStatus(s);
        setError(null);
      },
      (e: Error) => setError(e.message),
    );
  }, []);
  useEffect(load, [load]);

  const changes = status?.overridesActive ?? 0;

  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setActionError(null);
    try {
      if (pending.kind === "switch") {
        await api.setDataSource(pending.to);
        // Every page, the sidebar badge and cached health show the old dataset: start fresh.
        window.location.reload();
        return;
      }
      setStatus(await api.resetAdmin());
      setPending(null);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <ErrorBanner title="Couldn't load the admin status" message={error}>
        <BannerButton onClick={load}>
          <RotateCw className="size-3.5" /> Try again
        </BannerButton>
      </ErrorBanner>
    );
  }

  if (!status) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <KpiSkeleton key={i} />
        ))}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:col-span-2 lg:col-span-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="mt-4 h-10 w-full" />
        </div>
      </div>
    );
  }

  const active = status.dataSource;
  const ms = status.lastOptimizeMs;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard
          label="Data source"
          value={active ? SOURCE_LABEL[active] : "—"}
          hint={status.dataNote ?? health?.dataNote ?? (readOnly ? "From mock file" : undefined)}
          icon={Database}
        />
        <KpiCard
          label="Last solve time"
          value={ms === null || ms === undefined ? "—" : `${ms} ms`}
          hint={ms === null || ms === undefined ? "No optimization run since startup" : "Duration of the last /optimize"}
          icon={Timer}
          tone="neutral"
        />
        <KpiCard
          label="Manual changes"
          value={status.overridesActive ?? "—"}
          hint="Drivers and buses changed since the last reset"
          icon={PencilLine}
          tone={changes > 0 ? "warning" : "positive"}
        />
      </div>

      <Card title="Records" subtitle="What the engines run on right now">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {COUNT_LABELS.map(([key, label]) => (
            <div key={key} className="rounded-lg bg-slate-50 px-4 py-3">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="mt-1 text-2xl font-semibold text-slate-900 tabular-nums">{status.counts?.[key]?.toLocaleString("en-GB") ?? "—"}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Data source" subtitle="Switching reloads the backend's data and clears all manual changes">
          <div role="radiogroup" aria-label="Data source" className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
            {(Object.keys(SOURCE_LABEL) as DataSourceName[]).map((name) => (
              <button
                key={name}
                role="radio"
                aria-checked={active === name}
                disabled={readOnly || active === name}
                onClick={() => {
                  setActionError(null);
                  setPending({ kind: "switch", to: name });
                }}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-default ${
                  active === name ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600 hover:text-slate-900 disabled:opacity-60"
                }`}
              >
                {SOURCE_LABEL[name]}
              </button>
            ))}
          </div>
          {readOnly && <p className="mt-3 text-xs text-slate-500">Needs the live backend.</p>}
        </Card>

        <Card title="Manual changes" subtitle="Admin edits and emergency changes live in memory only">
          <button
            onClick={() => {
              setActionError(null);
              setPending({ kind: "reset" });
            }}
            disabled={readOnly || changes === 0}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RotateCcw className="size-4" /> Reset all changes
          </button>
          <p className="mt-3 text-xs text-slate-500">
            {changes > 0 ? "Restores the data files' values for every driver and bus." : "Nothing to reset."}
          </p>
        </Card>
      </div>

      <ConfirmDialog
        open={pending !== null}
        title={pending?.kind === "switch" ? `Switch to ${SOURCE_LABEL[pending.to].toLowerCase()}?` : "Reset all changes?"}
        confirmLabel={pending?.kind === "switch" ? "Switch data source" : "Reset"}
        danger={pending?.kind === "reset"}
        busy={busy}
        error={actionError}
        onConfirm={confirm}
        onCancel={() => setPending(null)}
      >
        {pending?.kind === "switch" ? (
          <p>
            The backend reloads its data{changes > 0 ? ` and clears ${changes} manual change${changes === 1 ? "" : "s"}` : ""}. Every
            page then shows the new dataset. A server restart goes back to the setting in <code>.env</code>.
          </p>
        ) : (
          <p>
            Clears {changes} manual change{changes === 1 ? "" : "s"} (admin edits and emergency changes). Results go back to the data
            files&apos; values.
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}
