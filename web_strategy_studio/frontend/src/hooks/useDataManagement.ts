/**
 * useDataManagement — custom hook for the data management panel.
 *
 * Manages paginated stock listing with search, sorting, batch selection,
 * batch delete, and download operations.  All state is kept in-component
 * (not in a global store) because it is panel-scoped.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

import {
  batchDeleteLocalStocks,
  downloadLocalData,
  fetchLocalData,
  type DownloadResponse,
  type LocalStockInfo,
} from "../api/dataApi";

const PER_PAGE = 50;

export function useDataManagement() {
  const qc = useQueryClient();

  // ---------- query params ----------
  const [page, setPage] = useState(1);
  const [search, setSearchRaw] = useState("");
  const [sortBy, setSortBy] = useState("code");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // ---------- selection ----------
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());

  // ---------- data query ----------
  const { data, isLoading, error } = useQuery({
    queryKey: ["local-data", page, search, sortBy, sortOrder],
    queryFn: () =>
      fetchLocalData({
        page,
        per_page: PER_PAGE,
        search: search || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
    placeholderData: (prev) => prev, // keep previous data while refetching
  });

  const stocks: LocalStockInfo[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  // ---------- search handler (resets page) ----------
  const setSearch = useCallback((value: string) => {
    setSearchRaw(value);
    setPage(1);
  }, []);

  // ---------- sort handler ----------
  const handleSort = useCallback(
    (column: string) => {
      if (sortBy === column) {
        setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setSortBy(column);
        setSortOrder("asc");
      }
      setPage(1);
    },
    [sortBy]
  );

  // ---------- selection handlers ----------
  const toggleSelect = useCallback((code: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedCodes(new Set(stocks.map((s) => s.code)));
  }, [stocks]);

  const deselectAll = useCallback(() => {
    setSelectedCodes(new Set());
  }, []);

  const allSelected = useMemo(
    () => stocks.length > 0 && stocks.every((s) => selectedCodes.has(s.code)),
    [stocks, selectedCodes]
  );

  // ---------- batch delete mutation ----------
  const deleteMut = useMutation({
    mutationFn: (codes: string[]) => batchDeleteLocalStocks(codes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["local-data"] });
      setSelectedCodes(new Set());
    },
  });

  const handleBatchDelete = useCallback(() => {
    const codes = Array.from(selectedCodes);
    if (codes.length === 0) return;
    deleteMut.mutate(codes);
  }, [selectedCodes, deleteMut]);

  // ---------- download mutation ----------
  const downloadMut = useMutation({
    mutationFn: async (params: {
      codes: string[];
      start_date?: string;
      end_date?: string;
    }) =>
      downloadLocalData(params.codes, {
        start_date: params.start_date || undefined,
        end_date: params.end_date || undefined,
      }),
    onSuccess: (_resp: DownloadResponse) => {
      qc.invalidateQueries({ queryKey: ["local-data"] });
    },
  });

  return {
    // data
    stocks,
    total,
    totalPages,
    page,
    isLoading,
    error,

    // pagination
    setPage,
    perPage: PER_PAGE,

    // search
    search,
    setSearch,

    // sort
    sortBy,
    sortOrder,
    handleSort,

    // selection
    selectedCodes,
    toggleSelect,
    selectAll,
    deselectAll,
    allSelected,

    // batch delete
    handleBatchDelete,
    isDeleting: deleteMut.isPending,
    deleteResult: deleteMut.data,

    // download
    downloadStocks: downloadMut.mutate,
    isDownloading: downloadMut.isPending,
    downloadResult: downloadMut.data,
  };
}
