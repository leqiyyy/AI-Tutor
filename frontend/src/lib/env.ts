import type { ApiMode } from "@/types/api";

const rawApiMode = (import.meta.env.VITE_API_MODE || "mock").toLowerCase();

export const appEnv = {
  apiMode: (rawApiMode === "live" ? "live" : "mock") as ApiMode,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "/api",
  authStorageKey: import.meta.env.VITE_AUTH_STORAGE_KEY || "luoying.session",
  mockLatencyMs: Number(import.meta.env.VITE_MOCK_LATENCY_MS || 700),
};

export const shouldUseMockApi = appEnv.apiMode === "mock";
