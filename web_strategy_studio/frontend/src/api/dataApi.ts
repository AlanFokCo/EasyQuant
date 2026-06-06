/** Data management API client — paginated, searchable, with batch operations. */

import { apiJson } from "./client";

export type LocalStockInfo = {
  code: string;
  start_date: string | null;
  end_date: string | null;
  size_bytes: number;
  size_human: string;
};

export type PaginatedStocks = {
  items: LocalStockInfo[];
  total: number;
  page: number;
  per_page: number;
};

export type DownloadResponse = {
  ok: boolean;
  downloaded: string[];
  merged: string[];
  failed: Array<{ code: string; error: string }>;
};

export type BatchDeleteResponse = {
  deleted: number;
  deleted_codes: string[];
  failed: Array<{ code: string; error: string }>;
};

export type QualityCheck = {
  name: string;
  passed: boolean;
  message: string;
};

export type QualityReport = {
  code: string;
  exists: boolean;
  checks: QualityCheck[];
  score: number;
  message: string;
};

export type ListStocksParams = {
  page?: number;
  per_page?: number;
  search?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  adjust?: string;
};

export async function fetchLocalData(params: ListStocksParams = {}): Promise<PaginatedStocks> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.per_page) query.set("per_page", String(params.per_page));
  if (params.search) query.set("search", params.search);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
  if (params.adjust) query.set("adjust", params.adjust);

  const qs = query.toString();
  return apiJson(`/api/v1/data/local${qs ? `?${qs}` : ""}`);
}

export async function fetchLocalStockDetail(
  code: string,
  adjust = "qfq"
): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/data/local/${code}?adjust=${adjust}`);
}

export async function fetchDataQuality(code: string, adjust = "qfq"): Promise<QualityReport> {
  return apiJson(`/api/v1/data/local/${code}/quality?adjust=${adjust}`);
}

export async function downloadLocalData(
  securities: string[],
  opts?: { start_date?: string; end_date?: string; adjust?: string }
): Promise<DownloadResponse> {
  return apiJson("/api/v1/data/local/download", {
    method: "POST",
    body: JSON.stringify({
      securities,
      start_date: opts?.start_date || null,
      end_date: opts?.end_date || null,
      adjust: opts?.adjust || "qfq",
    }),
  });
}

export async function batchDeleteLocalStocks(
  codes: string[],
  adjust = "qfq"
): Promise<BatchDeleteResponse> {
  return apiJson("/api/v1/data/local/batch-delete", {
    method: "POST",
    body: JSON.stringify({ codes, adjust }),
  });
}

export async function deleteLocalStock(
  code: string,
  adjust = "qfq"
): Promise<{ ok: boolean; message: string }> {
  return apiJson(`/api/v1/data/local/${code}?adjust=${adjust}`, { method: "DELETE" });
}
