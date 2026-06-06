/**
 * ReportPage — standalone route for /runs/:run_id/report.
 *
 * Renders the backtest report using the native ReportViewer (lightweight-charts)
 * or falls back to the iframe-based HTML report. Supports export and comparison.
 */
import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ExternalLink, ArrowLeft, Copy, Check, Download } from "lucide-react";

import { apiJson, getToken, resolveArtifactUrl } from "../api/client";
import { useTheme } from "../hooks/useTheme";
import ReportViewer from "../components/ReportViewer";
import ReportComparison from "../components/ReportComparison";

type RunInfo = {
  run_id: string;
  strategy_id: string;
  strategy_name: string | null;
  status: string;
  progress: number;
  stage: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
};

type RunMetrics = {
  run_id: string;
  status: string;
  metrics: Record<string, number | null>;
  raw: Record<string, unknown>;
};

const METRIC_LABELS: Record<string, string> = {
  total_return:   "总收益率",
  annual_return:  "年化收益率",
  sharpe_ratio:   "夏普比率",
  max_drawdown:   "最大回撤",
  calmar_ratio:   "卡玛比率",
};

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

function fmtNum(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(3);
}

export default function ReportPage() {
  useTheme(); // apply data-theme to <html>

  const { run_id } = useParams<{ run_id: string }>();
  const navigate = useNavigate();

  const [runInfo, setRunInfo] = useState<RunInfo | null>(null);
  const [metrics, setMetrics] = useState<RunMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"charts" | "html" | "compare">("charts");
  const [compareIds] = useState<string[]>([]);
  const [exporting, setExporting] = useState<string | null>(null);

  // Load run info and metrics
  useEffect(() => {
    if (!run_id) return;

    let cancelled = false;

    async function load() {
      try {
        const [info, met] = await Promise.all([
          apiJson<RunInfo>(`/api/v1/runs/${run_id}`),
          apiJson<RunMetrics>(`/api/v1/runs/${run_id}/metrics`).catch(() => null),
        ]);
        if (!cancelled) {
          setRunInfo(info);
          setMetrics(met);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "加载失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [run_id]);

  const reportApiUrl = (() => {
    if (!run_id) return undefined;
    const fromInfo = (runInfo as (RunInfo & { html_report_url?: string }) | null)?.html_report_url;
    if (fromInfo) return resolveArtifactUrl(fromInfo);
    return resolveArtifactUrl(`/api/v1/reports/${run_id}/report.html`);
  })();

  // Blob URL for the iframe fallback
  const [blobSrc, setBlobSrc] = useState<string | undefined>(undefined);
  useEffect(() => {
    if (!reportApiUrl || viewMode !== "html") return;
    let objectUrl: string | undefined;
    let cancelled = false;

    async function loadBlob() {
      try {
        const token = getToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(reportApiUrl!, { headers });
        if (!res.ok) return;
        const blob = await res.blob();
        if (!cancelled) {
          objectUrl = URL.createObjectURL(blob);
          setBlobSrc(objectUrl);
        }
      } catch (err) {
        console.error("[ReportPage] Failed to load report blob:", err);
      }
    }

    loadBlob();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [reportApiUrl, viewMode]);

  function copyShareLink() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  // Export handler for HTML/PDF downloads
  const handleExport = useCallback(async (fmt: string) => {
    if (!run_id) return;
    setExporting(fmt);
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const url = resolveArtifactUrl(`/api/v1/reports/${run_id}/export/${fmt}`);
      if (!url) throw new Error("Invalid export URL");
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `report_${run_id}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (e) {
      console.error("[ReportPage] Export failed:", e);
    } finally {
      setExporting(null);
    }
  }, [run_id]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--text-secondary)" }}>
        加载中…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100vh", gap: 12 }}>
        <p style={{ color: "var(--state-error)" }}>{error}</p>
        <button type="button" onClick={() => navigate(-1)} style={btnGhost}>
          <ArrowLeft size={14} /> 返回
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "0 16px",
          height: 48,
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <button
          type="button"
          aria-label="返回工作台"
          onClick={() => navigate("/")}
          style={btnGhost}
        >
          <ArrowLeft size={14} />
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 0 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" aria-hidden="true">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {runInfo?.strategy_name ?? "回测报告"} — 回测报告
          </span>
          {runInfo?.status && (
            <span
              aria-label={`状态: ${runInfo.status}`}
              style={{
                fontSize: 11,
                padding: "1px 6px",
                borderRadius: "var(--radius-sm)",
                background: runInfo.status === "succeeded" ? "var(--state-success-bg)" : "var(--state-error-bg)",
                color: runInfo.status === "succeeded" ? "var(--state-success)" : "var(--state-error)",
                border: "1px solid",
                borderColor: runInfo.status === "succeeded" ? "var(--state-success)" : "var(--state-error)",
                flexShrink: 0,
              }}
            >
              {runInfo.status === "succeeded" ? "成功" : runInfo.status === "failed" ? "失败" : runInfo.status}
            </span>
          )}
        </div>

        {/* View mode switcher */}
        <div style={{ display: "flex", gap: 2, background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)", padding: 2 }}>
          {(["charts", "html"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              style={{
                padding: "3px 10px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: viewMode === mode ? "var(--bg-secondary)" : "transparent",
                color: viewMode === mode ? "var(--text)" : "var(--text-secondary)",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: viewMode === mode ? 600 : 400,
              }}
            >
              {mode === "charts" ? "图表" : "HTML"}
            </button>
          ))}
        </div>

        {/* Key metric chips */}
        {metrics?.metrics && (
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            {Object.entries(METRIC_LABELS).slice(0, 3).map(([key, label]) => {
              const v = metrics.metrics[key];
              if (v == null) return null;
              return (
                <span
                  key={key}
                  title={label}
                  style={{
                    fontSize: 11,
                    padding: "2px 8px",
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-secondary)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {label} <strong style={{ color: "var(--text)" }}>{key.includes("return") || key === "max_drawdown" ? fmtPct(v) : fmtNum(v)}</strong>
                </span>
              );
            })}
          </div>
        )}

        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          {/* Export buttons */}
          <button
            type="button"
            aria-label="导出 HTML"
            onClick={() => handleExport("html")}
            disabled={!!exporting}
            style={btnGhost}
          >
            <Download size={14} />
            {exporting === "html" ? "..." : "HTML"}
          </button>
          <button
            type="button"
            aria-label="导出 JSON"
            onClick={() => handleExport("json")}
            disabled={!!exporting}
            style={btnGhost}
          >
            {exporting === "json" ? "..." : "JSON"}
          </button>

          {/* Copy share link */}
          <button
            type="button"
            aria-label="复制分享链接"
            onClick={copyShareLink}
            style={btnGhost}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "已复制" : "分享"}
          </button>

          {/* Open in new tab */}
          {run_id && (
            <button
              type="button"
              aria-label="在新标签页打开报告"
              onClick={() => {
                window.open(`/runs/${run_id}/report`, "_blank", "noopener,noreferrer");
              }}
              style={btnGhost}
            >
              <ExternalLink size={14} />
            </button>
          )}

          {/* Rerun */}
          <button
            type="button"
            aria-label="返回编辑器重新运行"
            onClick={() => navigate("/")}
            style={btnPrimary}
          >
            重新运行
          </button>
        </div>
      </header>

      {/* Content */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {viewMode === "charts" && run_id && (
          <ReportViewer runId={run_id} jsonUrl={null} />
        )}

        {viewMode === "html" && (
          blobSrc ? (
            <iframe
              title="回测 HTML 报告"
              src={blobSrc}
              sandbox="allow-scripts"
              style={{
                width: "100%",
                height: "100%",
                border: "none",
                background: "#fff",
              }}
            />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-secondary)", fontSize: 13 }}>
              加载 HTML 报告中…
            </div>
          )
        )}

        {viewMode === "compare" && (
          <ReportComparison
            runIds={compareIds.length >= 2 ? compareIds : run_id ? [run_id] : []}
            onClose={() => setViewMode("charts")}
          />
        )}
      </div>
    </div>
  );
}

const btnGhost: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  padding: "5px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "transparent",
  color: "var(--text-secondary)",
  fontSize: 12,
  cursor: "pointer",
  whiteSpace: "nowrap",
  transition: "color var(--motion-fast), border-color var(--motion-fast)",
};

const btnPrimary: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  padding: "5px 12px",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "var(--primary)",
  color: "#fff",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
  whiteSpace: "nowrap",
};
