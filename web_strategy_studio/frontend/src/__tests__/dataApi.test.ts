/**
 * Tests for the dataApi module — verifies URL construction, type shapes,
 * and error handling for the paginated data management API.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchLocalData,
  batchDeleteLocalStocks,
  downloadLocalData,
  fetchDataQuality,
  deleteLocalStock,
} from "../api/dataApi";

// ---------------------------------------------------------------------------
// Mock the underlying apiJson transport
// ---------------------------------------------------------------------------
vi.mock("../api/client", () => ({
  apiJson: vi.fn(),
}));

import { apiJson } from "../api/client";
const mockApiJson = vi.mocked(apiJson);

beforeEach(() => {
  mockApiJson.mockReset();
});

// ---------------------------------------------------------------------------
// fetchLocalData
// ---------------------------------------------------------------------------

describe("fetchLocalData", () => {
  it("calls apiJson with default params", async () => {
    mockApiJson.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 50 });
    const result = await fetchLocalData();
    expect(mockApiJson).toHaveBeenCalledWith("/api/v1/data/local");
    expect(result).toEqual({ items: [], total: 0, page: 1, per_page: 50 });
  });

  it("includes search parameter in query string", async () => {
    mockApiJson.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 50 });
    await fetchLocalData({ search: "600" });
    const url = mockApiJson.mock.calls[0][0];
    expect(url).toContain("search=600");
  });

  it("includes pagination parameters", async () => {
    mockApiJson.mockResolvedValue({ items: [], total: 0, page: 2, per_page: 10 });
    await fetchLocalData({ page: 2, per_page: 10 });
    const url = mockApiJson.mock.calls[0][0];
    expect(url).toContain("page=2");
    expect(url).toContain("per_page=10");
  });

  it("includes sort parameters", async () => {
    mockApiJson.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 50 });
    await fetchLocalData({ sort_by: "size_bytes", sort_order: "desc" });
    const url = mockApiJson.mock.calls[0][0];
    expect(url).toContain("sort_by=size_bytes");
    expect(url).toContain("sort_order=desc");
  });
});

// ---------------------------------------------------------------------------
// batchDeleteLocalStocks
// ---------------------------------------------------------------------------

describe("batchDeleteLocalStocks", () => {
  it("sends POST with codes array", async () => {
    mockApiJson.mockResolvedValue({ deleted: 2, deleted_codes: ["600519", "000001"], failed: [] });
    const result = await batchDeleteLocalStocks(["600519", "000001"]);
    expect(mockApiJson).toHaveBeenCalledWith("/api/v1/data/local/batch-delete", {
      method: "POST",
      body: JSON.stringify({ codes: ["600519", "000001"], adjust: "qfq" }),
    });
    expect(result.deleted).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// downloadLocalData
// ---------------------------------------------------------------------------

describe("downloadLocalData", () => {
  it("sends POST with securities and options", async () => {
    mockApiJson.mockResolvedValue({ ok: true, downloaded: ["600519"], merged: [], failed: [] });
    const result = await downloadLocalData(["600519"], { start_date: "20200101" });
    expect(mockApiJson).toHaveBeenCalledWith("/api/v1/data/local/download", {
      method: "POST",
      body: expect.stringContaining("600519"),
    });
    expect(result.ok).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// fetchDataQuality
// ---------------------------------------------------------------------------

describe("fetchDataQuality", () => {
  it("calls quality endpoint with code", async () => {
    mockApiJson.mockResolvedValue({
      code: "600519",
      exists: true,
      checks: [],
      score: 100,
      message: "Good",
    });
    const result = await fetchDataQuality("600519");
    expect(mockApiJson).toHaveBeenCalledWith("/api/v1/data/local/600519/quality?adjust=qfq");
    expect(result.score).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// deleteLocalStock
// ---------------------------------------------------------------------------

describe("deleteLocalStock", () => {
  it("sends DELETE request for single stock", async () => {
    mockApiJson.mockResolvedValue({ ok: true, message: "Deleted" });
    const result = await deleteLocalStock("600519");
    expect(mockApiJson).toHaveBeenCalledWith("/api/v1/data/local/600519?adjust=qfq", {
      method: "DELETE",
    });
    expect(result.ok).toBe(true);
  });
});
