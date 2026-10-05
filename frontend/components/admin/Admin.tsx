"use client";

import { useSyncExternalStore } from "react";
import { PageHeader } from "@/components/PageHeader";
import { BusesTab } from "./BusesTab";
import { DriversTab } from "./DriversTab";
import { StationsRoutesTab } from "./StationsRoutesTab";
import { StatusTab } from "./StatusTab";

const TABS = [
  { id: "status", label: "Status", Panel: StatusTab },
  { id: "drivers", label: "Drivers", Panel: DriversTab },
  { id: "buses", label: "Buses", Panel: BusesTab },
  { id: "stations-routes", label: "Stations & Routes", Panel: StationsRoutesTab },
] as const;
type TabId = (typeof TABS)[number]["id"];

const isTab = (id: string): id is TabId => TABS.some((t) => t.id === id);

// The active tab lives in the URL hash, so a reload (e.g. after switching the data source) and the
// banner's "Review" link (/admin#drivers) land on the right tab.
const hashStore = {
  subscribe(listener: () => void) {
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  },
  get(): TabId {
    const id = window.location.hash.slice(1);
    return isTab(id) ? id : "status";
  },
};

export function Admin() {
  const tab = useSyncExternalStore(hashStore.subscribe, hashStore.get, () => "status" as TabId);

  function select(id: TabId) {
    history.replaceState(null, "", `#${id}`);
    window.dispatchEvent(new HashChangeEvent("hashchange")); // replaceState doesn't fire it
  }

  const { Panel } = TABS.find((t) => t.id === tab)!;
  return (
    <>
      <PageHeader
        title="Admin"
        description="Inspect the data the engines run on and make temporary changes. Changes stay in memory and are never written to the data files."
      />
      <div role="tablist" aria-label="Admin sections" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => select(t.id)}
            className={`-mb-px shrink-0 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        <Panel />
      </div>
    </>
  );
}
