import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { fetchRunMetrics } from "../api/client";
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

export function MetricsComparison() {
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const compareIds = useEditorStore((s) => s.compareIds);

  // Fetch each run's metrics
  const metricsQueries = compareIds.map((id) =>
    useQuery({
      queryKey: ["run-metrics", id],
      queryFn: () => fetchRunMetrics(id),
      enabled: !!id,
      refetchOnWindowFocus: false,
    })
  );

  const allLoaded = metricsQueries.every((q) => !q.isLoading && !q.isFetching);
  const runs = useMemo(
    () =>
      metricsQueries
        .filter((q) => q.data)
        .map((q) => ({
          runId: q.data!.run_id,
          metrics: q.data!.metrics,
        })),
    [metricsQueries]
  );

  const keys = useMemo(() => {
    const set = new Set<string>();
    for (const r of runs) Object.keys(r.metrics).forEach((k) => set.add(k));
    // Order by known metrics first
    const ordered = Object.keys(METRIC_LABELS).filter((k) => set.has(k));
    for (const k of set) {
      if (!ordered.includes(k)) ordered.push(k);
    }
    return ordered;
  }, [runs]);

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
        {!allLoaded && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
            加载指标数据中…
          </div>
        )}
        {allLoaded && runs.length === 0 && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
            请在回测历史中选择至少 2 个回测进行对比
          </div>
        )}
        {allLoaded && runs.length > 0 && (
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
                    key={r.runId}
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
                    {r.runId.slice(0, 14)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
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
                        key={r.runId}
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
