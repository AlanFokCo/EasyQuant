export const apiOrigin = import.meta.env.VITE_API_ORIGIN || "";
export const apiV1 = `${apiOrigin}/api/v1`;

/** Structured API error carrying the backend {error:{code,message,details}} envelope. */
export class ApiError extends Error {
  readonly code: string;
  readonly details: unknown;
  constructor(code: string, message: string, details: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
  }
}

/** Absolute URL for opening / embedding reports (iframe, window.open). */
export function resolveArtifactUrl(path: string | undefined | null): string | undefined {
  if (!path?.trim()) return undefined;
  const p = path.trim();
  if (p.startsWith("http://") || p.startsWith("https://")) return p;
  if (!p.startsWith("/")) return undefined;
  const base = apiOrigin.replace(/\/$/, "");
  if (base) return `${base}${p}`;
  if (typeof window !== "undefined") return `${window.location.origin}${p}`;
  return p;
}

/** Get stored JWT token from localStorage. */
export function getToken(): string | null {
  return localStorage.getItem("eq_studio_token");
}

/** Store or clear JWT token. */
export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem("eq_studio_token", token);
  } else {
    localStorage.removeItem("eq_studio_token");
  }
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${apiOrigin}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    let body: {
      error?: { code?: string; message?: string; details?: unknown };
      detail?: { error?: { code?: string; message?: string; details?: unknown } };
    } | null = null;
    try {
      body = await res.json();
    } catch {
      /* ignore parse failure */
    }
    // Support both top-level error and FastAPI's nested detail.error envelope
    const err = body?.error ?? body?.detail?.error;
    if (err?.message) {
      throw new ApiError(
        err.code ?? "ERROR",
        err.message,
        err.details ?? null,
      );
    }
    throw new ApiError("HTTP_ERROR", `${res.status} ${res.statusText}`, null);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Typed helpers for runs
// ---------------------------------------------------------------------------

export type RunListItem = {
  run_id: string;
  strategy_id: string;
  strategy_name: string | null;
  status: string;
  progress: number;
  stage: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  queue_position: number | null; // B18
};

export async function fetchRunsList(
  strategyId?: string,
  limit = 100,
  offset = 0
): Promise<{ runs: RunListItem[]; total: number }> {
  const params = new URLSearchParams();
  if (strategyId) params.set("strategy_id", strategyId);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return apiJson(`/api/v1/runs?${params.toString()}`);
}

export async function fetchRunMetrics(runId: string): Promise<{
  run_id: string;
  status: string;
  metrics: Record<string, number | null>;
  raw: Record<string, unknown>;
}> {
  return apiJson(`/api/v1/runs/${runId}/metrics`);
}

// B22: equity curve point
export type EquityCurvePoint = { date: string; value: number };

export async function compareRunMetrics(runIds: string[]): Promise<{
  runs: {
    run_id: string;
    strategy_name: string | null;
    status: string;
    started_at: string | null;
    metrics: Record<string, number | null>;
    equity_curve: EquityCurvePoint[]; // B22
  }[];
  common_keys: string[];
}> {
  return apiJson("/api/v1/runs/compare", {
    method: "POST",
    body: JSON.stringify({ run_ids: runIds }),
  });
}
