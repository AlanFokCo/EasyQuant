/** Data management API client. */

import { apiJson } from "./client";

export type LocalStockInfo = {
  code: string;
  start_date: string | null;
  end_date: string | null;
  size_bytes: number;
  size_human: string;
};

export type DownloadResponse = {
  ok: boolean;
  downloaded: string[];
  merged: string[];
  failed: Array<{ code: string; error: string }>;
};

export async function fetchLocalData(): Promise<LocalStockInfo[]> {
  return apiJson("/api/v1/data/local");
}

export async function fetchLocalStockDetail(code: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/v1/data/local/${code}`);
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

export async function deleteLocalStock(code: string): Promise<{ ok: boolean; message: string }> {
  return apiJson(`/api/v1/data/local/${code}`, { method: "DELETE" });
}
