import type {
  Dashboard,
  EmergencyRequest,
  EmergencyResult,
  IdleDrivers,
  LotseResult,
  OptimizeRequest,
  OptimizeResult,
} from "./types";

// The one setting: leave NEXT_PUBLIC_API_BASE_URL unset to use the mock files
// in public/mock/, or set it (e.g. http://localhost:8000) to hit the backend.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
export const USE_MOCK = !API_BASE_URL;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  mock: string,
  init?: { method?: "GET" | "POST"; body?: unknown; query?: Record<string, string | undefined> },
): Promise<T> {
  let url: string;
  let options: RequestInit = {};

  if (USE_MOCK) {
    // Mock files are static, so every call (including POSTs) is a plain GET.
    url = `/mock/${mock}.json`;
  } else {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(init?.query ?? {})) {
      if (value !== undefined) params.set(key, value);
    }
    const qs = params.toString();
    url = `${API_BASE_URL}${path}${qs ? `?${qs}` : ""}`;
    options = {
      method: init?.method ?? "GET",
      headers: { "Content-Type": "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    };
  }

  const res = await fetch(url, { ...options, cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.error ?? "HTTP_ERROR", err.message ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getDashboard: (date?: string) =>
    request<Dashboard>("/dashboard", "dashboard", { query: { date } }),

  getIdleDrivers: (date?: string) =>
    request<IdleDrivers>("/idle-drivers", "idle-drivers", { query: { date } }),

  optimize: (body: OptimizeRequest = {}) =>
    request<OptimizeResult>("/optimize", "optimize", { method: "POST", body }),

  reportEmergency: (body: EmergencyRequest) =>
    request<EmergencyResult>("/emergency", "emergency", { method: "POST", body }),

  // Lotse is the UI name; the backend endpoint and mock file are still "copilot".
  askLotse: (question: string) =>
    request<LotseResult>("/copilot", "copilot", { method: "POST", body: { question } }),
};
