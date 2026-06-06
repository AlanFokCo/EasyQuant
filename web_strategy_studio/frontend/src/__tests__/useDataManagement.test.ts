/**
 * Tests for the useDataManagement hook.
 *
 * We test the hook's state management logic: pagination, search reset,
 * sort toggling, and selection handling.
 */
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mock the data API
// ---------------------------------------------------------------------------
vi.mock("../api/dataApi", () => ({
  fetchLocalData: vi.fn().mockResolvedValue({
    items: [
      { code: "600519", start_date: "2020-01-01", end_date: "2024-12-31", size_bytes: 1024, size_human: "1.0KB" },
      { code: "000001", start_date: "2019-01-01", end_date: "2024-12-31", size_bytes: 2048, size_human: "2.0KB" },
    ],
    total: 2,
    page: 1,
    per_page: 50,
  }),
  batchDeleteLocalStocks: vi.fn().mockResolvedValue({
    deleted: 1,
    deleted_codes: ["600519"],
    failed: [],
  }),
  downloadLocalData: vi.fn().mockResolvedValue({
    ok: true,
    downloaded: ["600519"],
    merged: [],
    failed: [],
  }),
}));

// Zustand store mock — just the addToast function
vi.mock("../store/editorStore", () => ({
  useEditorStore: vi.fn((selector: (s: { addToast: (type: string, msg: string) => void }) => unknown) =>
    selector({ addToast: vi.fn() })
  ),
}));

import { useDataManagement } from "../hooks/useDataManagement";
import { fetchLocalData } from "../api/dataApi";

// ---------------------------------------------------------------------------
// Helper: create a wrapper with QueryClientProvider
// ---------------------------------------------------------------------------
function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

beforeEach(() => {
  vi.mocked(fetchLocalData).mockClear();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDataManagement", () => {
  it("starts at page 1 with default sort", async () => {
    const { result } = renderHook(() => useDataManagement(), {
      wrapper: createWrapper(),
    });

    expect(result.current.page).toBe(1);
    expect(result.current.sortBy).toBe("code");
    expect(result.current.sortOrder).toBe("asc");
  });

  it("updates search and resets page", async () => {
    const { result } = renderHook(() => useDataManagement(), {
      wrapper: createWrapper(),
    });

    // Move to page 2 first
    act(() => {
      result.current.setPage(2);
    });
    expect(result.current.page).toBe(2);

    // Search should reset page to 1
    act(() => {
      result.current.setSearch("600");
    });
    expect(result.current.page).toBe(1);
    expect(result.current.search).toBe("600");
  });

  it("toggles sort direction on same column", async () => {
    const { result } = renderHook(() => useDataManagement(), {
      wrapper: createWrapper(),
    });

    expect(result.current.sortOrder).toBe("asc");

    act(() => {
      result.current.handleSort("code");
    });
    expect(result.current.sortOrder).toBe("desc");

    act(() => {
      result.current.handleSort("code");
    });
    expect(result.current.sortOrder).toBe("asc");
  });

  it("changes sort column and resets to asc", async () => {
    const { result } = renderHook(() => useDataManagement(), {
      wrapper: createWrapper(),
    });

    // Set desc on code
    act(() => {
      result.current.handleSort("code");
    });
    expect(result.current.sortOrder).toBe("desc");

    // Switch to size_bytes — should reset to asc
    act(() => {
      result.current.handleSort("size_bytes");
    });
    expect(result.current.sortBy).toBe("size_bytes");
    expect(result.current.sortOrder).toBe("asc");
  });

  it("manages selection state", async () => {
    const { result } = renderHook(() => useDataManagement(), {
      wrapper: createWrapper(),
    });

    expect(result.current.selectedCodes.size).toBe(0);

    // Toggle one
    act(() => {
      result.current.toggleSelect("600519");
    });
    expect(result.current.selectedCodes.has("600519")).toBe(true);

    // Toggle again (deselect)
    act(() => {
      result.current.toggleSelect("600519");
    });
    expect(result.current.selectedCodes.has("600519")).toBe(false);
  });

  it("selectAll and deselectAll", async () => {
    const { result } = renderHook(() => useDataManagement(), {
      wrapper: createWrapper(),
    });

    // Wait for data to load
    await vi.waitFor(() => {
      expect(result.current.stocks.length).toBeGreaterThan(0);
    });

    act(() => {
      result.current.selectAll();
    });
    expect(result.current.allSelected).toBe(true);

    act(() => {
      result.current.deselectAll();
    });
    expect(result.current.selectedCodes.size).toBe(0);
    expect(result.current.allSelected).toBe(false);
  });
});
