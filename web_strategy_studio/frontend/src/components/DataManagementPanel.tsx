/**
 * DataManagementPanel — right-panel view for managing local CSV data.
 *
 * Features:
 * - List of all local stocks with date range and file size
 * - Search/filter by code
 * - Download dialog for fetching new data
 * - Delete local data
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Virtuoso } from "react-virtuoso";

import {
  fetchLocalData,
  downloadLocalData,
  deleteLocalStock,
  type LocalStockInfo,
  type DownloadResponse,
} from "../api/dataApi";
import { useEditorStore } from "../store/editorStore";

export function DataManagementPanel() {
  const qc = useQueryClient();
  const addToast = useEditorStore((s) => s.addToast);
  const [search, setSearch] = useState("");
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [dlCode, setDlCode] = useState("");
  const [dlStart, setDlStart] = useState("");
  const [dlEnd, setDlEnd] = useState("");

  const { data: stocks, isLoading } = useQuery({
    queryKey: ["local-data"],
    queryFn: fetchLocalData,
  });

  const downloadMut = useMutation({
    mutationFn: async () => {
      const codes = dlCode
        .split(/[,，\s]+/)
        .map((c) => c.trim().replace(/\.(XSHG|XSHE)/i, ""))
        .filter(Boolean);
      if (!codes.length) throw new Error("请输入至少一只股票代码");
      return downloadLocalData(codes, {
        start_date: dlStart || undefined,
        end_date: dlEnd || undefined,
      });
    },
    onSuccess: (resp: DownloadResponse) => {
      qc.invalidateQueries({ queryKey: ["local-data"] });
      setDownloadOpen(false);
      const msgs: string[] = [];
      if (resp.downloaded.length) msgs.push(`下载: ${resp.downloaded.join(", ")}`);
      if (resp.merged.length) msgs.push(`合并: ${resp.merged.join(", ")}`);
      if (resp.failed.length) msgs.push(`失败: ${resp.failed.map((f) => f.code).join(", ")}`);
      addToast(resp.ok ? "success" : "error", msgs.join("; ") || "操作完成");
    },
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "下载失败");
    },
  });

  const deleteMut = useMutation({
    mutationFn: (code: string) => deleteLocalStock(code),
    onSuccess: (_resp, code) => {
      qc.invalidateQueries({ queryKey: ["local-data"] });
      addToast("success", `已删除 ${code}`);
    },
    onError: (_e: unknown, code: string) => {
      addToast("error", `删除 ${code} 失败`);
    },
  });

  const filtered = (stocks ?? []).filter((s) =>
    s.code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 0 }}>
      {/* Header */}
      <div
        style={{
          padding: "12px 12px 8px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>数据管理</h3>
          <button
            type="button"
            onClick={() => setDownloadOpen(true)}
            style={{
              padding: "4px 12px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--primary)",
              color: "#fff",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            下载数据
          </button>
        </div>
        <input
          placeholder="搜索股票代码，如 600519"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: "100%",
            padding: "6px 8px",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text)",
            fontSize: 12,
            boxSizing: "border-box",
          }}
        />
        <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
          共 {filtered.length} 只股票有本地数据
        </span>
      </div>

      {/* Stock list */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {isLoading ? (
          <div style={{ padding: 20, textAlign: "center", color: "var(--text-dim)", fontSize: 12 }}>
            加载中…
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--text-dim)", fontSize: 12 }}>
            {search ? "未找到匹配的股票" : "暂无本地数据，点击上方「下载数据」开始"}
          </div>
        ) : (
          <Virtuoso
            data={filtered}
            itemContent={(_index, item: LocalStockInfo) => (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "8px 12px",
                  borderBottom: "1px solid var(--border)",
                  fontSize: 12,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: "var(--text)" }}>{item.code}</div>
                  <div style={{ color: "var(--text-dim)", fontSize: 11, marginTop: 2 }}>
                    {item.start_date ?? "—"} → {item.end_date ?? "—"} · {item.size_human}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => deleteMut.mutate(item.code)}
                  style={{
                    padding: "2px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid rgba(248,81,73,0.3)",
                    background: "transparent",
                    color: "var(--state-error)",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  删除
                </button>
              </div>
            )}
          />
        )}
      </div>

      {/* Download dialog */}
      {downloadOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 2000,
          }}
          onClick={() => setDownloadOpen(false)}
        >
          <div
            style={{
              background: "var(--bg-secondary)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
              padding: 20,
              width: 400,
              maxWidth: "90vw",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>下载数据</h3>
            <label style={{ display: "block", marginBottom: 8, fontSize: 12, color: "var(--text-secondary)" }}>
              股票代码（多只用逗号或空格分隔）
              <input
                value={dlCode}
                onChange={(e) => setDlCode(e.target.value)}
                placeholder="如 600519, 000858"
                style={{
                  width: "100%",
                  marginTop: 4,
                  padding: "6px 8px",
                  background: "var(--bg)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--text)",
                  fontSize: 12,
                  boxSizing: "border-box",
                }}
              />
            </label>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <label style={{ flex: 1, fontSize: 12, color: "var(--text-secondary)" }}>
                开始日期
                <input
                  type="date"
                  value={dlStart}
                  onChange={(e) => setDlStart(e.target.value)}
                  style={{
                    width: "100%",
                    marginTop: 4,
                    padding: "6px 8px",
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text)",
                    fontSize: 12,
                    boxSizing: "border-box",
                  }}
                />
              </label>
              <label style={{ flex: 1, fontSize: 12, color: "var(--text-secondary)" }}>
                结束日期
                <input
                  type="date"
                  value={dlEnd}
                  onChange={(e) => setDlEnd(e.target.value)}
                  style={{
                    width: "100%",
                    marginTop: 4,
                    padding: "6px 8px",
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text)",
                    fontSize: 12,
                    boxSizing: "border-box",
                  }}
                />
              </label>
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setDownloadOpen(false)}
                style={{
                  padding: "6px 16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--text-secondary)",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => downloadMut.mutate()}
                disabled={downloadMut.isPending}
                style={{
                  padding: "6px 16px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: downloadMut.isPending ? "var(--text-dim)" : "var(--primary)",
                  color: "#fff",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: downloadMut.isPending ? "not-allowed" : "pointer",
                }}
              >
                {downloadMut.isPending ? "下载中…" : "下载"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
