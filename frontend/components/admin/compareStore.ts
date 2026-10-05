"use client";

import { api } from "@/lib/api";
import type { OptimizeResult } from "@/lib/types";

/**
 * Before/after optimization around admin edits, shared by the Drivers and Buses tabs.
 * `previous` is the last /optimize result we have; the first edit fetches it first, so "before"
 * really is the state before the change. A page reload (reset, data-source switch) starts over.
 */
export interface CompareState {
  previous: OptimizeResult | null;
  /** Successful edits since `previous` was computed. */
  pending: number;
  running: boolean;
  error: string | null;
  /** The last comparison, shown until the next edit. */
  last: { before: OptimizeResult | null; after: OptimizeResult } | null;
}

let state: CompareState = { previous: null, pending: 0, running: false, error: null, last: null };
const listeners = new Set<() => void>();

function update(patch: Partial<CompareState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export const compareStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  get: () => state,
};

const SERVER_STATE: CompareState = { previous: null, pending: 0, running: false, error: null, last: null };
export const serverCompareState = () => SERVER_STATE;

let baseline: Promise<void> | null = null;

/** Call before a PATCH: makes sure there's a "before" result. Failures just mean no comparison. */
export function ensureBaseline(): Promise<void> {
  if (state.previous) return Promise.resolve();
  baseline ??= api
    .optimize()
    .then((previous) => update({ previous }))
    .catch(() => {})
    .finally(() => {
      baseline = null;
    });
  return baseline;
}

/** Call after a successful PATCH. */
export function noteChange() {
  update({ pending: state.pending + 1, last: null, error: null });
}

export async function rerunOptimization() {
  update({ running: true, error: null });
  try {
    const after = await api.optimize();
    update({ last: { before: state.previous, after }, previous: after, pending: 0, running: false });
  } catch (e) {
    update({ running: false, error: (e as Error).message });
  }
}

/** Express trips per day in the recommended launch plan. */
export function plannedExpressTrips(result: OptimizeResult) {
  return (result.recommendations ?? [])
    .filter((r) => result.recommended?.includes(r.route))
    .reduce((n, r) => n + (r.tripsCovered ?? 0), 0);
}
