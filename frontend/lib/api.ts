import type {
  AdminBus,
  AdminDriver,
  AdminListQuery,
  AdminPage,
  AdminRoute,
  AdminStation,
  AdminStatus,
  ApiErrorBody,
  BusPatch,
  DataSourceName,
  DriverPatch,
  Health,
  Dashboard,
  EmergencyRequest,
  EmergencyResult,
  IdleDrivers,
  LotseResult,
  OptimizeRequest,
  OptimizeResult,
} from "./types";

// FastAPI backend. Override with NEXT_PUBLIC_API_BASE_URL (see .env.example).
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
// NEXT_PUBLIC_USE_MOCKS=true skips the backend and serves public/mock/*.json only.
const MOCKS_ONLY = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

const DEFAULT_TIMEOUT_MS = 8_000;

/** A request the backend answered with an error (4xx/5xx), or that failed outright. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// --- Where the last response came from, for the sidebar badge ------------------

export type DataSource = { kind: "live" } | { kind: "mock"; reason: string };

let dataSource: DataSource | null = MOCKS_ONLY ? { kind: "mock", reason: "Mock mode is on" } : null;
const listeners = new Set<() => void>();

function setDataSource(next: DataSource) {
  const reason = (s: DataSource | null) => (s?.kind === "mock" ? s.reason : undefined);
  if (dataSource?.kind === next.kind && reason(dataSource) === reason(next)) return;
  dataSource = next;
  listeners.forEach((l) => l());
}

export const dataSourceStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  get: () => dataSource,
};

// --- Request helper -------------------------------------------------------------

interface RequestOptions<T> {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, string | undefined>;
  timeoutMs?: number;
  /** Adjusts mock data to the request, e.g. search/paginate a mock list. */
  fromMock?: (data: T) => T;
}

/** Network failures, timeouts and server errors fall back to mocks; 4xx (bad input, conflicts) don't. */
function shouldFallBack(err: unknown) {
  return !(err instanceof ApiError) || (err.status >= 500 && err.status !== 501);
}

function describe(err: unknown) {
  if (err instanceof ApiError) return `${err.status} ${err.code}: ${err.message}`;
  if (err instanceof DOMException && err.name === "TimeoutError") return "Request timed out";
  return `Backend unreachable at ${API_BASE_URL}`;
}

async function fetchJson<T>(url: string, init: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  if (!res.ok) {
    const body: Partial<ApiErrorBody> = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.error ?? "HTTP_ERROR", body.message ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

async function fetchMock<T>(mock: string): Promise<T> {
  // Mock files are static, so every call (including POSTs) is a plain GET.
  return fetchJson<T>(`/mock/${mock}.json`, {});
}

async function request<T>(path: string, mock: string, opts: RequestOptions<T> = {}): Promise<T> {
  const mockData = async () => (opts.fromMock ?? ((d: T) => d))(await fetchMock<T>(mock));
  if (MOCKS_ONLY) return mockData();

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(opts.query ?? {})) {
    if (value !== undefined) params.set(key, value);
  }
  const qs = params.toString();

  try {
    const data = await fetchJson<T>(`${API_BASE_URL}${path}${qs ? `?${qs}` : ""}`, {
      method: opts.method ?? "GET",
      headers: { "Content-Type": "application/json" },
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: AbortSignal.timeout(opts.timeoutMs ?? DEFAULT_TIMEOUT_MS),
    });
    setDataSource({ kind: "live" });
    return data;
  } catch (err) {
    if (!shouldFallBack(err)) throw err;
    const reason = describe(err);
    console.warn(`[api] ${opts.method ?? "GET"} ${path} failed (${reason}); using /mock/${mock}.json`);
    try {
      const data = await mockData();
      setDataSource({ kind: "mock", reason });
      return data;
    } catch {
      throw new ApiError(err instanceof ApiError ? err.status : 0, "UNAVAILABLE", `${reason}, and no mock data is available.`);
    }
  }
}

/** Writes (PATCH, switch, reset) never fall back to mocks: a change that didn't happen must not look saved. */
async function mutate<T>(path: string, method: "POST" | "PATCH", body?: unknown): Promise<T> {
  if (MOCKS_ONLY) throw new ApiError(0, "MOCK_MODE", "Mock mode is on: changes need the live backend.");
  try {
    const data = await fetchJson<T>(`${API_BASE_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
    setDataSource({ kind: "live" });
    return data;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, "UNAVAILABLE", `${describe(err)}: the change was not saved.`);
  }
}

// --- Admin status store: drives the "manual changes active" banner on every page ---

let adminStatus: AdminStatus | null = null;
const adminListeners = new Set<() => void>();

function setAdminStatus(next: AdminStatus | null) {
  adminStatus = next;
  adminListeners.forEach((l) => l());
}

export const adminStatusStore = {
  subscribe(listener: () => void) {
    adminListeners.add(listener);
    return () => adminListeners.delete(listener);
  },
  get: () => adminStatus,
};

/** Re-read /admin/status in the background (after any change); failures just hide the banner. */
export function refreshAdminStatus() {
  api.getAdminStatus().catch(() => setAdminStatus(null));
}

/** Mock lists hold (at most) one page of the default data: apply search and paging locally. */
function pageLocally<T>({ q, page = 1, pageSize = 20 }: AdminListQuery) {
  return (data: AdminPage<T>): AdminPage<T> => {
    const needle = q?.trim().toLowerCase();
    const all = data.items ?? [];
    const matches = needle
      ? all.filter((item) =>
          Object.values(item as object).some(
            (v) => (typeof v === "string" || typeof v === "number") && String(v).toLowerCase().includes(needle),
          ),
        )
      : all;
    const start = (page - 1) * pageSize;
    // total counts what the mock file holds, so paging never runs past the rows we have
    return { page, pageSize, total: matches.length, items: matches.slice(start, start + pageSize) };
  };
}

function listQuery({ page, pageSize, q }: AdminListQuery) {
  return { page: page?.toString(), pageSize: pageSize?.toString(), q: q?.trim() || undefined };
}

function list<T>(path: string, mock: string, query: AdminListQuery) {
  return request<AdminPage<T>>(path, mock, { query: listQuery(query), fromMock: pageLocally<T>(query) });
}

// --- Endpoints ------------------------------------------------------------------

export const api = {
  /** Which dataset the backend runs on. Never falls back to mocks: null means no backend. */
  getHealth: async (): Promise<Health | null> => {
    if (MOCKS_ONLY) return null;
    try {
      return await fetchJson<Health>(`${API_BASE_URL}/health`, { signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) });
    } catch {
      return null;
    }
  },

  getDashboard: (date?: string) => request<Dashboard>("/dashboard", "dashboard", { query: { date } }),

  getIdleDrivers: (date?: string) => request<IdleDrivers>("/idle-drivers", "idle-drivers", { query: { date } }),

  // CP-SAT solve can take a few seconds.
  optimize: (body: OptimizeRequest = {}) =>
    request<OptimizeResult>("/optimize", "optimize", { method: "POST", body, timeoutMs: 30_000 }),

  reportEmergency: async (body: EmergencyRequest) => {
    const result = await request<EmergencyResult>("/emergency", "emergency", { method: "POST", body });
    refreshAdminStatus(); // a breakdown changes the bus pool: the overrides banner should show it
    return result;
  },

  /** Demo helper: undo all breakdowns and dispatches on the backend. No-op without a backend. */
  resetEmergency: async (): Promise<void> => {
    if (MOCKS_ONLY) return;
    try {
      await fetchJson(`${API_BASE_URL}/emergency/reset`, {
        method: "POST",
        signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
      });
      setDataSource({ kind: "live" });
      refreshAdminStatus();
    } catch (err) {
      if (!shouldFallBack(err)) throw err;
      setDataSource({ kind: "mock", reason: describe(err) });
    }
  },

  // Lotse is the UI name; the backend endpoint and mock file are still "copilot".
  askLotse: (question: string) =>
    request<LotseResult>("/copilot", "copilot", { method: "POST", body: { question } }),

  // --- Admin (API_CONTRACT.md section 6); mocks in public/mock/admin/ ---

  getAdminStatus: async () => {
    const status = await request<AdminStatus>("/admin/status", "admin/status");
    setAdminStatus(status);
    return status;
  },

  setDataSource: async (dataSource: DataSourceName) => {
    const status = await mutate<AdminStatus>("/admin/data-source", "POST", { dataSource });
    setAdminStatus(status);
    return status;
  },

  resetAdmin: async () => {
    const status = await mutate<AdminStatus>("/admin/reset", "POST");
    setAdminStatus(status);
    return status;
  },

  getAdminDrivers: (query: AdminListQuery = {}) => list<AdminDriver>("/admin/drivers", "admin/drivers", query),
  getAdminBuses: (query: AdminListQuery = {}) => list<AdminBus>("/admin/buses", "admin/buses", query),
  getAdminStations: (query: AdminListQuery = {}) => list<AdminStation>("/admin/stations", "admin/stations", query),
  getAdminRoutes: (query: AdminListQuery = {}) => list<AdminRoute>("/admin/routes", "admin/routes", query),

  patchDriver: async (id: string, patch: DriverPatch) => {
    const driver = await mutate<AdminDriver>(`/admin/drivers/${encodeURIComponent(id)}`, "PATCH", patch);
    refreshAdminStatus();
    return driver;
  },

  patchBus: async (id: string, patch: BusPatch) => {
    const bus = await mutate<AdminBus>(`/admin/buses/${encodeURIComponent(id)}`, "PATCH", patch);
    refreshAdminStatus();
    return bus;
  },
};
