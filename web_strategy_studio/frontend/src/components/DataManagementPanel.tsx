/**
 * DataManagementPanel -- right-panel view for managing local CSV data.
 *
 * Features:
 * - Paginated list with server-side search and sorting
 * - Batch selection and batch delete
 * - Download dialog for fetching new data
 * - Per-stock data quality report
 * - Virtual scrolling via react-virtuoso for large datasets
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Virtuoso } from "react-virtuoso";

import { fetchDataQuality, type LocalStockInfo } from "../api/dataApi";
import { useDataManagement } from "../hooks/useDataManagement";
import { useEditorStore } from "../store/editorStore";

// ---------------------------------------------------------------------------
// Inline style constants (dark theme via CSS vars)
// ---------------------------------------------------------------------------
const S = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100%",
    gap: 0,
  },
  header: {
    padding: "12px 12px 8px",
    borderBottom: "1px solid var(--border)",
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    margin: 0,
    fontSize: 14,
    fontWeight: 600,
  },
  searchInput: {
    width: "100%",
    padding: "6px 8px",
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 12,
    boxSizing: "border-box" as const,
  },
  stats: {
    fontSize: 11,
    color: "var(--text-dim)",
  },
  tableHeader: {
    display: "flex",
    alignItems: "center",
    padding: "6px 12px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-secondary)",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-dim)",
    userSelect: "none" as const,
  },
  row: {
    display: "flex",
    alignItems: "center",
    padding: "8px 12px",
    borderBottom: "1px solid var(--border)",
    fontSize: 12,
  },
  colCheckbox: { width: 32, flexShrink: 0, display: "flex", alignItems: "center" },
  colCode: { width: 80, flexShrink: 0, fontWeight: 600, color: "var(--text)" },
  colDates: { flex: 1, color: "var(--text-dim)", fontSize: 11 },
  colSize: { width: 70, flexShrink: 0, textAlign: "right" as const, color: "var(--text-dim)", fontSize: 11 },
  colQuality: { width: 50, flexShrink: 0, textAlign: "center" as const },
  colActions: { width: 60, flexShrink: 0, textAlign: "right" as const },
  sortIndicator: { marginLeft: 4, fontSize: 10 },
  empty: {
    padding: 40,
    textAlign: "center" as const,
    color: "var(--text-dim)",
    fontSize: 12,
  },
  pagination: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 12px",
    borderTop: "1px solid var(--border)",
    fontSize: 11,
    color: "var(--text-dim)",
  },
  btn: {
    padding: "4px 12px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border)",
    background: "transparent",
    color: "var(--text-secondary)",
    fontSize: 12,
    cursor: "pointer",
  },
  btnPrimary: {
    padding: "4px 12px",
    borderRadius: "var(--radius-sm)",
    border: "none",
    background: "var(--primary)",
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnDanger: {
    padding: "4px 12px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid rgba(248,81,73,0.3)",
    background: "transparent",
    color: "var(--state-error)",
    fontSize: 11,
    cursor: "pointer",
  },
  btnSmall: {
    padding: "2px 8px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border)",
    background: "transparent",
    color: "var(--text-dim)",
    fontSize: 11,
    cursor: "pointer",
  },
  disabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  // Download dialog
  overlay: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(0,0,0,0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2000,
  },
  dialog: {
    background: "var(--bg-secondary)",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--border)",
    padding: 20,
    width: 400,
    maxWidth: "90vw",
  },
  dialogTitle: { margin: "0 0 12px", fontSize: 14, fontWeight: 600 },
  label: { display: "block", marginBottom: 8, fontSize: 12, color: "var(--text-secondary)" },
  dialogInput: {
    width: "100%",
    marginTop: 4,
    padding: "6px 8px",
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 12,
    boxSizing: "border-box" as const,
  },
};

// ---------------------------------------------------------------------------
// Quality badge
// ---------------------------------------------------------------------------

function QualityBadge({ code }: { code: string }) {
  const { data } = useQuery({
    queryKey: ["quality", code],
    queryFn: () => fetchDataQuality(code),
    staleTime: 5 * 60 * 1000,
  });

  if (!data) return null;

  const color =
    data.score >= 75
      ? "var(--state-success, #3fb950)"
      : data.score >= 50
        ? "var(--state-warning, #d29922)"
        : "var(--state-error, #f85149)";

  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        cursor: "help",
      }}
      title={`Quality: ${data.message} (${data.score}/100)`}
    />
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function DataManagementPanel() {
  const addToast = useEditorStore((s) => s.addToast);

  const {
    stocks,
    total,
    totalPages,
    page,
    isLoading,
    setPage,
    search,
    setSearch,
    sortBy,
    sortOrder,
    handleSort,
    selectedCodes,
    toggleSelect,
    selectAll,
    deselectAll,
    allSelected,
    handleBatchDelete,
    isDeleting,
    downloadStocks,
    isDownloading,
  } = useDataManagement();

  // ---------- Download dialog ----------
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [dlCode, setDlCode] = useState("");
  const [dlStart, setDlStart] = useState("");
  const [dlEnd, setDlEnd] = useState("");

  const handleDownload = () => {
    const codes = dlCode
      .split(/[,，\s]+/)
      .map((c) => c.trim().replace(/\.(XSHG|XSHE)/i, ""))
      .filter(Boolean);
    if (!codes.length) {
      addToast("error", "请输入至少一只股票代码");
      return;
    }
    downloadStocks(
      { codes, start_date: dlStart || undefined, end_date: dlEnd || undefined },
      {
        onSuccess: (resp) => {
          setDownloadOpen(false);
          setDlCode("");
          const msgs: string[] = [];
          if (resp.downloaded.length) msgs.push(`下载: ${resp.downloaded.join(", ")}`);
          if (resp.merged.length) msgs.push(`合并: ${resp.merged.join(", ")}`);
          if (resp.failed.length) msgs.push(`失败: ${resp.failed.map((f) => f.code).join(", ")}`);
          addToast(resp.ok ? "success" : "error", msgs.join("; ") || "操作完成");
        },
        onError: (e: unknown) => {
          addToast("error", e instanceof Error ? e.message : "下载失败");
        },
      }
    );
  };

  const handleBatchDeleteWithConfirm = () => {
    const count = selectedCodes.size;
    if (count === 0) return;
    if (!window.confirm(`确定要删除选中的 ${count} 条数据吗？`)) return;
    handleBatchDelete();
    addToast("info", `正在删除 ${count} 条数据…`);
  };

  const sortLabel = (col: string) =>
    sortBy === col ? (sortOrder === "asc" ? " ↑" : " ↓") : "";

  return (
    <div style={S.container}>
      {/* ---- Header ---- */}
      <div style={S.header}>
        <div style={S.toolbar}>
          <h3 style={S.title}>数据管理</h3>
          <div style={{ display: "flex", gap: 8 }}>
            {selectedCodes.size > 0 && (
              <button
                type="button"
                onClick={handleBatchDeleteWithConfirm}
                disabled={isDeleting}
                style={{
                  ...S.btnDanger,
                  ...(isDeleting ? S.disabled : {}),
                }}
              >
                删除选中 ({selectedCodes.size})
              </button>
            )}
            <button type="button" onClick={() => setDownloadOpen(true)} style={S.btnPrimary}>
              下载数据
            </button>
          </div>
        </div>
        <input
          placeholder="搜索股票代码或名称，如 600519"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={S.searchInput}
        />
        <span style={S.stats}>
          共 {total} 只股票有本地数据
          {selectedCodes.size > 0 && ` · 已选 ${selectedCodes.size}`}
        </span>
      </div>

      {/* ---- Table header ---- */}
      <div style={S.tableHeader}>
        <div style={S.colCheckbox}>
          <input
            type="checkbox"
            checked={allSelected}
            onChange={() => (allSelected ? deselectAll() : selectAll())}
          />
        </div>
        <div
          style={{ ...S.colCode, cursor: "pointer" }}
          onClick={() => handleSort("code")}
        >
          代码{sortLabel("code")}
        </div>
        <div style={S.colDates}>日期范围</div>
        <div
          style={{ ...S.colSize, cursor: "pointer" }}
          onClick={() => handleSort("size_bytes")}
        >
          大小{sortLabel("size_bytes")}
        </div>
        <div style={S.colQuality}>质量</div>
        <div style={S.colActions} />
      </div>

      {/* ---- Stock list ---- */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {isLoading && stocks.length === 0 ? (
          <div style={S.empty}>加载中...</div>
        ) : stocks.length === 0 ? (
          <div style={S.empty}>
            {search ? "未找到匹配的股票" : "暂无本地数据，点击上方「下载数据」开始"}
          </div>
        ) : (
          <Virtuoso
            data={stocks}
            itemContent={(_index, item: LocalStockInfo) => (
              <StockRow
                item={item}
                selected={selectedCodes.has(item.code)}
                onToggle={toggleSelect}
              />
            )}
          />
        )}
      </div>

      {/* ---- Pagination ---- */}
      {totalPages > 1 && (
        <div style={S.pagination}>
          <button
            type="button"
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            style={{ ...S.btnSmall, ...(page <= 1 ? S.disabled : {}) }}
          >
            上一页
          </button>
          <span>
            第 {page} / {totalPages} 页
          </span>
          <button
            type="button"
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            style={{ ...S.btnSmall, ...(page >= totalPages ? S.disabled : {}) }}
          >
            下一页
          </button>
        </div>
      )}

      {/* ---- Download dialog ---- */}
      {downloadOpen && (
        <div style={S.overlay} onClick={() => setDownloadOpen(false)}>
          <div style={S.dialog} onClick={(e) => e.stopPropagation()}>
            <h3 style={S.dialogTitle}>下载数据</h3>
            <label style={S.label}>
              股票代码（多只用逗号或空格分隔）
              <input
                value={dlCode}
                onChange={(e) => setDlCode(e.target.value)}
                placeholder="如 600519, 000858"
                style={S.dialogInput}
              />
            </label>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <label style={{ flex: 1, ...S.label }}>
                开始日期
                <input
                  type="date"
                  value={dlStart}
                  onChange={(e) => setDlStart(e.target.value)}
                  style={S.dialogInput}
                />
              </label>
              <label style={{ flex: 1, ...S.label }}>
                结束日期
                <input
                  type="date"
                  value={dlEnd}
                  onChange={(e) => setDlEnd(e.target.value)}
                  style={S.dialogInput}
                />
              </label>
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" onClick={() => setDownloadOpen(false)} style={S.btn}>
                取消
              </button>
              <button
                type="button"
                onClick={handleDownload}
                disabled={isDownloading}
                style={{
                  ...S.btnPrimary,
                  ...(isDownloading ? S.disabled : {}),
                  background: isDownloading ? "var(--text-dim)" : "var(--primary)",
                }}
              >
                {isDownloading ? "下载中..." : "下载"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StockRow sub-component
// ---------------------------------------------------------------------------

function StockRow({
  item,
  selected,
  onToggle,
}: {
  item: LocalStockInfo;
  selected: boolean;
  onToggle: (code: string) => void;
}) {
  const addToast = useEditorStore((s) => s.addToast);

  // Single-stock delete (uses batch-delete under the hood via the API)
  const handleSingleDelete = async () => {
    try {
      const { batchDeleteLocalStocks } = await import("../api/dataApi");
      await batchDeleteLocalStocks([item.code]);
      addToast("success", `已删除 ${item.code}`);
    } catch {
      addToast("error", `删除 ${item.code} 失败`);
    }
  };

  return (
    <div style={S.row}>
      <div style={S.colCheckbox}>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(item.code)}
        />
      </div>
      <div style={S.colCode}>{item.code}</div>
      <div style={S.colDates}>
        {item.start_date ?? "—"} → {item.end_date ?? "—"}
      </div>
      <div style={S.colSize}>{item.size_human}</div>
      <div style={S.colQuality}>
        <QualityBadge code={item.code} />
      </div>
      <div style={S.colActions}>
        <button type="button" onClick={handleSingleDelete} style={S.btnSmall}>
          删除
        </button>
      </div>
    </div>
  );
}
