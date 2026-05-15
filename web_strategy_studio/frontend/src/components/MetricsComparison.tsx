import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { compareRunMetrics, EquityCurvePoint } from "../api/client";
import { useEditorStore } from "../store/editorStore";

const METRIC_LABELS: Record<string, string> = {
  total_return: "总收益率",
  annual_return: "年化收益率",
  annual_volatility: "年化波动率",
  sharpe_ratio: "夏普比率",
  sortino_ratio: "索提诺比率",
  max_drawdown: "最大回撤",
  calmar_ratio: "卡玛比率",
  alpha: "Alpha",
  beta: "Beta",
  information_ratio: "信息比率",
  win_rate_daily: "日胜率",
  win_rate_trade: "交易胜率",
};

const METRIC_FMT: Record<string, (v: number | null) => string> = {
  total_return: (v) => (v != null ? `${(v * 100).toFixed(2)}%` : "—"),
  annual_return: (v) => (v != null ? `${(v * 100).toFixed(2)}%` : "—"),
  annual_volatility: (v) => (v != null ? `${(v * 100).toFixed(2)}%` : "—"),
  sharpe_ratio: (v) => (v != null ? v.toFixed(3) : "—"),
  sortino_ratio: (v) => (v != null ? v.toFixed(3) : "—"),
  max_drawdown: (v) => (v != null ? `${(v * 100).toFixed(2)}%` : "—"),
  calmar_ratio: (v) => (v != null ? v.toFixed(3) : "—"),
  alpha: (v) => (v != null ? v.toFixed(4) : "—"),
  beta: (v) => (v != null ? v.toFixed(3) : "—"),
  information_ratio: (v) => (v != null ? v.toFixed(3) : "—"),
  win_rate_daily: (v) => (v != null ? `${(v * 100).toFixed(1)}%` : "—"),
  win_rate_trade: (v) => (v != null ? `${(v * 100).toFixed(1)}%` : "—"),
};

function isGood(metric: string, val: number | null | undefined): boolean {
  if (val == null) return false;
  if (["sharpe_ratio", "sortino_ratio", "calmar_ratio", "information_ratio", "alpha", "annual_return", "total_return", "win_rate_daily", "win_rate_trade"].includes(metric)) return val > 0;
  if (["max_drawdown", "annual_volatility", "beta"].includes(metric)) return val < 1;
  return false;
}

/** Minimal sparkline for the equity curve (SVG). */
function EquitySpark({ points }: { points: EquityCurvePoint[] }) {
  if (!points.length) return <span style={{ color: "var(--text-dim)", fontSize: 10 }}>—</span>;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 80;
  const h = 24;
  const path = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * w;
      const y = h - ((p.value - min) / range) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const lastVal = values[values.length - 1];
  const pct = ((lastVal - values[0]) / Math.abs(values[0] || 1)) * 100;
  const color = pct >= 0 ? "var(--success)" : "var(--error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, justifyContent: "center" }}>
      <svg width={w} height={h} style={{ display: "block" }}>
        <path d={path} stroke={color} strokeWidth={1.5} fill="none" />
      </svg>
      <span style={{ fontSize: 10, fontFamily: "var(--mono)", color }}>
        {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
      </span>
    </div>
  );
}

export function MetricsComparison() {
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const compareIds = useEditorStore((s) => s.compareIds);

  // B22: single compare call instead of N parallel fetchRunMetrics calls
  const { data, isLoading } = useQuery({
    queryKey: ["compare", ...compareIds],
    queryFn: () => compareRunMetrics(compareIds),
    enabled: compareIds.length >= 2,
    refetchOnWindowFocus: false,
  });

  const runs = useMemo(() => data?.runs ?? [], [data]);

  const keys = useMemo(() => {
    if (!data) return [];
    const ordered = Object.keys(METRIC_LABELS).filter((k) => data.common_keys.includes(k));
    for (const k of data.common_keys) {
      if (!ordered.includes(k)) ordered.push(k);
    }
    return ordered;
  }, [data]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 14px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>指标对比</h3>
        <button
          type="button"
          onClick={() => setShowCompare(false)}
          style={{
            padding: "4px 8px",
            borderRadius: 4,
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            fontSize: 12,
          }}
        >
          ×
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 14 }}>
        {isLoading && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
            加载指标数据中…
          </div>
        )}
        {!isLoading && compareIds.length < 2 && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
            请在回测历史中选择至少 2 个回测进行对比
          </div>
        )}
        {!isLoading && runs.length > 0 && (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    textAlign: "left",
                    padding: "6px 10px",
                    color: "var(--text-secondary)",
                    fontWeight: 600,
                    borderBottom: "1px solid var(--border)",
                    position: "sticky",
                    top: 0,
                    background: "var(--bg)",
                  }}
                >
                  指标
                </th>
                {runs.map((r) => (
                  <th
                    key={r.run_id}
                    style={{
                      textAlign: "center",
                      padding: "6px 10px",
                      color: "var(--text-secondary)",
                      fontWeight: 600,
                      borderBottom: "1px solid var(--border)",
                      fontFamily: "var(--mono)",
                      fontSize: 10,
                      position: "sticky",
                      top: 0,
                      background: "var(--bg)",
                    }}
                  >
                    {r.run_id.slice(0, 14)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* B22: equity curve row */}
              <tr>
                <td style={{ padding: "6px 10px", borderBottom: "1px solid var(--border-light)", color: "var(--text-secondary)", fontWeight: 500 }}>
                  净值曲线
                </td>
                {runs.map((r) => (
                  <td key={r.run_id} style={{ padding: "6px 10px", textAlign: "center", borderBottom: "1px solid var(--border-light)" }}>
                    <EquitySpark points={r.equity_curve ?? []} />
                  </td>
                ))}
              </tr>
              {keys.map((key) => (
                <tr key={key}>
                  <td
                    style={{
                      padding: "6px 10px",
                      borderBottom: "1px solid var(--border-light)",
                      color: "var(--text-secondary)",
                      fontWeight: 500,
                    }}
                  >
                    {METRIC_LABELS[key] ?? key}
                  </td>
                  {runs.map((r) => {
                    const val = r.metrics[key] ?? null;
                    const good = isGood(key, val);
                    return (
                      <td
                        key={r.run_id}
                        style={{
                          padding: "6px 10px",
                          textAlign: "center",
                          borderBottom: "1px solid var(--border-light)",
                          fontFamily: "var(--mono)",
                          color: good ? "var(--success)" : val === null ? "var(--text-dim)" : "var(--text)",
                          fontWeight: good ? 600 : 400,
                        }}
                      >
                        {METRIC_FMT[key] ? METRIC_FMT[key](val) : val != null ? String(val) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
