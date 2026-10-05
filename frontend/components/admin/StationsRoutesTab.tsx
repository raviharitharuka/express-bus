"use client";

import { RotateCw } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminListQuery, AdminPage, AdminRoute, AdminStation } from "@/lib/types";
import { Card } from "@/components/Card";
import { BannerButton, ErrorBanner } from "@/components/ErrorBanner";
import { AdminTable, Pagination, SearchBox, show, td, th } from "./ui";
import { usePagedList } from "./usePagedList";

export function StationsRoutesTab() {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <ReadOnlyList<AdminStation>
        title="Stations"
        subtitle="Bus and driver counts include manual changes"
        noun="stations"
        fetchPage={api.getAdminStations}
        head={["Station", "Buses", "Spare", "Drivers based"]}
        row={(s) => [
          <span key="name">
            <span className="font-medium text-slate-900">{show(s.name)}</span>
            <span className="block text-xs text-slate-400">{s.id}</span>
          </span>,
          show(s.totalBuses),
          show(s.spareBuses),
          show(s.driversBased),
        ]}
        rowKey={(s) => s.id ?? s.name ?? ""}
      />
      <ReadOnlyList<AdminRoute>
        title="Routes"
        subtitle="Regular lines; express candidates are tested on the Optimization page"
        noun="routes"
        fetchPage={api.getAdminRoutes}
        head={["Line", "From → To", "Distance", "Duration", "Every"]}
        row={(r) => [
          <span key="line" className="font-medium text-slate-900" title={r.name}>
            {show(r.routeId)}
          </span>,
          <span key="ends">
            {show(r.from)} → {show(r.to)}
          </span>,
          r.distanceKm === undefined ? "—" : `${r.distanceKm} km`,
          r.durationMin === undefined ? "—" : `${r.durationMin} min`,
          r.frequencyMin === undefined ? "—" : `${r.frequencyMin} min`,
        ]}
        rowKey={(r) => r.routeId ?? r.name ?? ""}
      />
    </div>
  );
}

function ReadOnlyList<T>({
  title,
  subtitle,
  noun,
  fetchPage,
  head,
  row,
  rowKey,
}: {
  title: string;
  subtitle: string;
  noun: string;
  fetchPage: (query: AdminListQuery) => Promise<AdminPage<T>>;
  head: string[];
  row: (item: T) => React.ReactNode[];
  rowKey: (item: T) => string;
}) {
  const list = usePagedList<T>(fetchPage);
  const items = list.data?.items ?? [];
  return (
    <Card title={title} subtitle={subtitle}>
      <div className="mb-4">
        <SearchBox value={list.search} onChange={list.setSearch} placeholder={`Search ${noun}…`} />
      </div>
      {list.error ? (
        <ErrorBanner title={`Couldn't load ${noun}`} message={list.error}>
          <BannerButton onClick={list.reload}>
            <RotateCw className="size-3.5" /> Try again
          </BannerButton>
        </ErrorBanner>
      ) : (
        <>
          <AdminTable
            loading={list.loading}
            hasData={list.data !== null}
            empty={items.length === 0 ? (list.q ? `No ${noun} match “${list.q}”.` : `No ${noun}.`) : null}
            head={head.map((h) => (
              <th key={h} className={th}>
                {h}
              </th>
            ))}
          >
            {items.map((item) => (
              <tr key={rowKey(item)}>
                {row(item).map((cell, i) => (
                  <td key={i} className={`${td} ${i > 0 ? "tabular-nums" : ""}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </AdminTable>
          {list.data && (
            <Pagination page={list.page} total={list.data.total ?? items.length} onPage={list.setPage} disabled={list.loading} />
          )}
        </>
      )}
    </Card>
  );
}
