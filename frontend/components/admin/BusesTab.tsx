"use client";

import { useState } from "react";
import { LoaderCircle, RotateCw } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminBus, BusStatus, BusStatusChange } from "@/lib/types";
import { useDataSource } from "@/components/DataSource";
import { BannerButton, ErrorBanner } from "@/components/ErrorBanner";
import { StatusBadge } from "@/components/StatusBadge";
import type { Tone } from "@/components/theme";
import { AdminTable, EditedBadge, Pagination, SearchBox, show, td, th } from "./ui";
import { usePagedList } from "./usePagedList";

const STATUS: Record<BusStatus, { label: string; tone: Tone }> = {
  active: { label: "On duty", tone: "brand" },
  spare: { label: "Spare", tone: "positive" },
  maintenance: { label: "Maintenance", tone: "warning" },
  broken: { label: "Broken", tone: "critical" },
};

/** The dropdown offers what PATCH accepts; on duty and spare are both "available". */
const CHANGE_OF: Record<BusStatus, BusStatusChange> = {
  active: "available",
  spare: "available",
  maintenance: "maintenance",
  broken: "broken",
};

export function BusesTab() {
  const list = usePagedList<AdminBus>(api.getAdminBuses);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const readOnly = useDataSource()?.kind === "mock";

  async function setStatus(bus: AdminBus, status: BusStatusChange) {
    if (!bus.busId) return;
    setSaving(bus.busId);
    setSaveError(null);
    try {
      const updated = await api.patchBus(bus.busId, { status });
      list.replaceItem((b) => b.busId === bus.busId, updated);
    } catch (e) {
      setSaveError(`${bus.busId}: ${(e as Error).message}`);
    } finally {
      setSaving(null);
    }
  }

  const items = list.data?.items ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SearchBox value={list.search} onChange={list.setSearch} placeholder="Search buses, stations, status…" />
        {readOnly && <p className="text-xs text-slate-500">Read-only: editing needs the live backend.</p>}
      </div>

      {saveError && (
        <ErrorBanner title="Change not saved" message={saveError}>
          <BannerButton onClick={() => setSaveError(null)}>Dismiss</BannerButton>
        </ErrorBanner>
      )}

      {list.error ? (
        <ErrorBanner title="Couldn't load buses" message={list.error}>
          <BannerButton onClick={list.reload}>
            <RotateCw className="size-3.5" /> Try again
          </BannerButton>
        </ErrorBanner>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <AdminTable
            loading={list.loading}
            hasData={list.data !== null}
            empty={items.length === 0 ? (list.q ? `No buses match “${list.q}”.` : "No buses.") : null}
            head={
              <>
                <th className={th}>Bus</th>
                <th className={th}>Station</th>
                <th className={th}>Type</th>
                <th className={th}>Capacity</th>
                <th className={th}>Status</th>
                <th className={th}>Change status</th>
              </>
            }
          >
            {items.map((b) => {
              const current = b.status ? STATUS[b.status] : null;
              return (
                <tr key={b.busId}>
                  <td className={`${td} font-medium whitespace-nowrap text-slate-900`}>
                    {show(b.busId)}
                    {b.overridden && <EditedBadge />}
                    {saving === b.busId && <LoaderCircle className="ml-2 inline size-3.5 animate-spin text-slate-400" />}
                  </td>
                  <td className={td}>{show(b.station)}</td>
                  <td className={`${td} capitalize`}>{show(b.type)}</td>
                  <td className={`${td} tabular-nums`}>{show(b.capacity)}</td>
                  <td className={td}>{current ? <StatusBadge tone={current.tone}>{current.label}</StatusBadge> : "—"}</td>
                  <td className={td}>
                    <select
                      aria-label={`Status of ${b.busId}`}
                      value={b.status ? CHANGE_OF[b.status] : ""}
                      disabled={readOnly || saving !== null || !b.status}
                      onChange={(e) => setStatus(b, e.target.value as BusStatusChange)}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm text-slate-700 shadow-sm focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <option value="available">Available</option>
                      <option value="maintenance">Maintenance</option>
                      <option value="broken">Broken</option>
                    </select>
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
