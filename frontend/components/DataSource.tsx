"use client";

import { useSyncExternalStore } from "react";
import { DatabaseZap } from "lucide-react";
import { API_BASE_URL, dataSourceStore } from "@/lib/api";
import { tone } from "@/components/theme";

export function useDataSource() {
  return useSyncExternalStore(dataSourceStore.subscribe, dataSourceStore.get, () => null);
}

/** Sidebar status: live backend, mock fallback, or not contacted yet. */
export function DataSourceBadge() {
  const source = useDataSource();
  const [dot, label] =
    source === null
      ? [tone.neutral.dot, "Connecting…"]
      : source.kind === "live"
        ? [tone.positive.dot, "Live backend"]
        : [tone.warning.dot, "Mock data"];

  return (
    <div
      title={source?.kind === "mock" ? source.reason : API_BASE_URL}
      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
    >
      <span className={`size-2 shrink-0 rounded-full ${dot}`} />
      {label}
    </div>
  );
}

/** Banner shown above every page while responses come from public/mock/. */
export function MockDataNotice() {
  const source = useDataSource();
  if (source?.kind !== "mock") return null;

  return (
    <div
      role="status"
      className={`mb-6 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${tone.warning.soft}`}
    >
      <DatabaseZap className="mt-0.5 size-4 shrink-0" />
      <p>
        <span className="font-medium">Showing demo data.</span> {source.reason}. Start the backend (
        <code className="font-mono text-xs">uvicorn main:app</code> in <code className="font-mono text-xs">backend/</code>)
        and retry to see live numbers.
      </p>
    </div>
  );
}
