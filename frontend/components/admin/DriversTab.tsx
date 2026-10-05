"use client";

import { useState } from "react";
import { LoaderCircle, Plus, RotateCw, X } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminDriver, DriverPatch } from "@/lib/types";
import { useDataSource } from "@/components/DataSource";
import { BannerButton, ErrorBanner } from "@/components/ErrorBanner";
import { OptimizeCompare } from "./OptimizeCompare";
import { ensureBaseline, noteChange } from "./compareStore";
import { AdminTable, EditedBadge, Pagination, SearchBox, show, td, th, Toggle } from "./ui";
import { usePagedList } from "./usePagedList";

export function DriversTab() {
  const list = usePagedList<AdminDriver>(api.getAdminDrivers);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const readOnly = useDataSource()?.kind === "mock";

  async function save(driver: AdminDriver, patch: DriverPatch) {
    if (!driver.driverId) return;
    setSaving(driver.driverId);
    setSaveError(null);
    try {
      await ensureBaseline(); // the "before" result for Re-run optimization
      const updated = await api.patchDriver(driver.driverId, patch);
      noteChange();
      list.replaceItem((d) => d.driverId === driver.driverId, updated);
    } catch (e) {
      setSaveError(`${driver.driverId}: ${(e as Error).message}`);
    } finally {
      setSaving(null);
    }
  }

  const items = list.data?.items ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SearchBox value={list.search} onChange={list.setSearch} placeholder="Search drivers, stations, duties…" />
        {readOnly && <p className="text-xs text-slate-500">Read-only: editing needs the live backend.</p>}
      </div>

      <OptimizeCompare />

      {saveError && (
        <ErrorBanner title="Change not saved" message={saveError}>
          <BannerButton onClick={() => setSaveError(null)}>Dismiss</BannerButton>
        </ErrorBanner>
      )}

      {list.error ? (
        <ErrorBanner title="Couldn't load drivers" message={list.error}>
          <BannerButton onClick={list.reload}>
            <RotateCw className="size-3.5" /> Try again
          </BannerButton>
        </ErrorBanner>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <AdminTable
            loading={list.loading}
            hasData={list.data !== null}
            empty={items.length === 0 ? (list.q ? `No drivers match “${list.q}”.` : "No drivers.") : null}
            head={
              <>
                <th className={th}>Driver</th>
                <th className={th}>Home station</th>
                <th className={th}>Today</th>
                <th className={th}>Max shift</th>
                <th className={th}>Overtime</th>
                <th className={th}>Vacation dates</th>
                <th className={th}>Unavailable (sick)</th>
              </>
            }
          >
            {items.map((d) => {
              const busy = saving === d.driverId;
              const disabled = readOnly || saving !== null;
              return (
                <tr key={d.driverId} className={d.available === false ? "bg-rose-50/50" : undefined}>
                  <td className={`${td} font-medium whitespace-nowrap text-slate-900`}>
                    {show(d.driverId)}
                    {d.overridden && <EditedBadge />}
                    {busy && <LoaderCircle className="ml-2 inline size-3.5 animate-spin text-slate-400" />}
                  </td>
                  <td className={td}>{show(d.homeStation)}</td>
                  <td className={`${td} whitespace-nowrap`}>{d.dutyId ?? <span className="text-slate-400">Off</span>}</td>
                  <td className={`${td} tabular-nums`}>{d.maxShiftHours === undefined ? "—" : `${d.maxShiftHours} h`}</td>
                  <td className={td}>
                    <Toggle
                      checked={d.overtimeAvailable ?? false}
                      onChange={(v) => save(d, { overtimeAvailable: v })}
                      label={`Overtime for ${d.driverId}`}
                      disabled={disabled || d.overtimeAvailable === undefined}
                    />
                  </td>
                  <td className={td}>
                    <VacationDates
                      dates={d.vacationDates ?? []}
                      disabled={disabled || d.vacationDates === undefined}
                      onChange={(vacationDates) => save(d, { vacationDates })}
                    />
                  </td>
                  <td className={td}>
                    <Toggle
                      checked={d.available === false}
                      onChange={(sick) => save(d, { available: !sick })}
                      label={`${d.driverId} unavailable (sick) until reset`}
                      disabled={disabled || d.available === undefined}
                      danger
                    />
                  </td>
                </tr>
              );
            })}
          </AdminTable>
          {list.data && (
            <Pagination page={list.page} total={list.data.total ?? items.length} onPage={list.setPage} disabled={list.loading} />
          )}
        </div>
      )}
    </div>
  );
}

function VacationDates({ dates, disabled, onChange }: { dates: string[]; disabled: boolean; onChange: (dates: string[]) => void }) {
  const [adding, setAdding] = useState(false);
  return (
    <div className="flex max-w-xs flex-wrap items-center gap-1.5">
      {dates.map((date) => (
        <span key={date} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700 tabular-nums">
          {date}
          <button
            onClick={() => onChange(dates.filter((d) => d !== date))}
            disabled={disabled}
            aria-label={`Remove ${date}`}
            className="text-slate-400 hover:text-rose-600 disabled:opacity-50"
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      {adding ? (
        <input
          type="date"
          autoFocus
          disabled={disabled}
          aria-label="Add vacation date"
          onBlur={() => setAdding(false)}
          onChange={(e) => {
            const date = e.target.value;
            if (!date) return;
            setAdding(false);
            if (!dates.includes(date)) onChange([...dates, date].sort());
          }}
          className="rounded-md border border-slate-200 px-1.5 py-0.5 text-xs"
        />
      ) : (
        <button
          onClick={() => setAdding(true)}
          disabled={disabled}
          className="inline-flex items-center gap-0.5 rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-xs text-slate-500 hover:border-indigo-300 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="size-3" /> Add
        </button>
      )}
    </div>
  );
}
