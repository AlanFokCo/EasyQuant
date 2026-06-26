/**
 * ReportComparison — side-by-side comparison of multiple backtest reports.
 *
 * Fetches metrics for each run via the /api/v1/reports/compare endpoint,
 * renders a comparison table and overlays equity curves on a shared chart.
 */
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, LineStyle } from "lightweight-charts";
import type { IChartApi } from "lightweight-charts";

import { apiJson } from "../api/client";

type CompareResult = {
  reports: {
    run_id: string;
    metrics?: Record<string, number | null>;
    cum_return_data?: { time: string; value: number }[];
    [key: string]: unknown;
  }[];
  differences: Record<
    string,
    { values: number[]; max: number; min: number; diff: number }
  >;
  error?: string;
};

const METRIC_LABELS: Record<string, string> = {
  total_return: "总收益率",
  annual_return: "年化收益率",
  sharpe_ratio: "夏普比率",
  max_drawdown: "最大回撤",
  sortino_ratio: "索提诺比率",
  calmar_ratio: "卡玛比率",
  annual_volatility: "年化波动率",
  win_rate: "胜率",
};

const METRIC_FMT: Record<string, (v: number) => string> = {
  total_return: (v) => `${(v * 100).toFixed(2)}%`,
  annual_return: (v) => `${(v * 100).toFixed(2)}%`,
  sharpe_ratio: (v) => v.toFixed(3),
  max_drawdown: (v) => `${(v * 100).toFixed(2)}%`,
  sortino_ratio: (v) => v.toFixed(3),
  calmar_ratio: (v) => v.toFixed(3),
  annual_volatility: (v) => `${(v * 100).toFixed(2)}%`,
  win_rate: (v) => `${(v * 100).toFixed(1)}%`,
};

const CHART_COLORS = ["#f5222d", "#1890ff", "#fa8c16", "#722ed1", "#52c41a", "#eb2f96"];

interface ReportComparisonProps {
  runIds: string[];
  onClose?: () => void;
}

export default function ReportComparison({ runIds, onClose }: ReportComparisonProps) {
  const [data, setData] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  // Fetch comparison data
  useEffect(() => {
    if (runIds.length < 2) return;
    let cancelled = false;

    async function load() {
      try {
        const result = await apiJson<CompareResult>("/api/v1/reports/compare", {
          method: "POST",
          body: JSON.stringify({ run_ids: runIds }),
        });
        if (!cancelled) {
          if (result.error) {
            setError(result.error);
          } else {
            setData(result);
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [runIds]);

  // Render overlay chart
  useEffect(() => {
    if (!data || !chartRef.current) return;

    if (chartApiRef.current) {
      chartApiRef.current.remove();
      chartApiRef.current = null;
    }

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 280,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8c8c8c",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(245,245,245,0.8)" },
        horzLines: { color: "rgba(245,245,245,0.8)" },
      },
      crosshair: {
        vertLine: { color: "#d9d9d9", width: 1, style: LineStyle.Dashed },
        horzLine: { color: "#d9d9d9", width: 1, style: LineStyle.Dashed },
      },
      timeScale: { borderColor: "#e8e8e8", barSpacing: 6 },
      rightPriceScale: { borderColor: "#e8e8e8" },
    });
    chartApiRef.current = chart;

    data.reports.forEach((report, i) => {
      const cumData = report.cum_return_data;
      if (cumData && cumData.length > 0) {
        const color = CHART_COLORS[i % CHART_COLORS.length];
        const series = chart.addLineSeries({
          color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          title: report.run_id.slice(0, 12),
        });
        series.setData(cumData);
      }
    });

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    ro.observe(chartRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartApiRef.current = null;
    };
  }, [data]);

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
          加载对比数据中…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={{ padding: 24, textAlign: "center", color: "var(--state-error)", fontSize: 13 }}>
          {error}
        </div>
      </div>
    );
  }

  if (!data || data.reports.length < 2) {
    return (
      <div style={styles.container}>
        <div style={{ padding: 24, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
          请选择至少 2 个回测进行对比
        </div>
      </div>
    );
  }

  // Collect all metric keys present in any report
  const allKeys = new Set<string>();
  data.reports.forEach((r) => {
    const m = r.metrics || {};
    Object.keys(m).forEach((k) => allKeys.add(k));
  });
  const metricKeys = Object.keys(METRIC_LABELS).filter((k) => allKeys.has(k));
  for (const k of allKeys) {
    if (!metricKeys.includes(k)) metricKeys.push(k);
  }

  // Find best values for highlighting
  const bestValues: Record<string, number> = {};
  metricKeys.forEach((key) => {
    const vals = data.reports
      .map((r) => r.metrics?.[key])
      .filter((v): v is number => v != null);
    if (vals.length > 0) {
      // For drawdown, lower (less negative) is better
      if (key === "max_drawdown") {
        bestValues[key] = Math.max(...vals);
      } else {
        bestValues[key] = Math.max(...vals);
      }
    }
  });

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
          报告对比 ({data.reports.length} 个)
        </h3>
        {onClose && (
          <button type="button" onClick={onClose} style={styles.closeBtn}>
            x
          </button>
        )}
      </div>

      {/* Overlay chart */}
      <div style={styles.chartPanel}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: "var(--text)" }}>
          累计收益率对比
        </div>
        <div ref={chartRef} style={{ width: "100%" }} />
        {/* Legend */}
        <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
          {data.reports.map((r, i) => (
            <span key={r.run_id} style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}>
              <span
                style={{
                  width: 12,
                  height: 3,
                  background: CHART_COLORS[i % CHART_COLORS.length],
                  borderRadius: 1,
                  display: "inline-block",
                }}
              />
              <span style={{ color: "var(--text-secondary)", fontFamily: "var(--mono)" }}>
                {r.run_id.slice(0, 14)}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Comparison table */}
      <div style={{ overflow: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>指标</th>
              {data.reports.map((r, i) => (
                <th key={r.run_id} style={{ ...styles.th, textAlign: "center" }}>
                  <span
                    style={{
                      display: "inline-block",
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: CHART_COLORS[i % CHART_COLORS.length],
                      marginRight: 6,
                    }}
                  />
                  {r.run_id.slice(0, 12)}
                </th>
              ))}
              <th style={{ ...styles.th, textAlign: "center" }}>差异</th>
            </tr>
          </thead>
          <tbody>
            {metricKeys.map((key) => {
              const diff = data.differences[key];
              return (
                <tr key={key}>
                  <td style={styles.td}>
                    {METRIC_LABELS[key] ?? key}
                  </td>
                  {data.reports.map((r) => {
                    const val = r.metrics?.[key] ?? null;
                    const isBest = val != null && val === bestValues[key];
                    const fmt = METRIC_FMT[key];
                    return (
                      <td
                        key={r.run_id}
                        style={{
                          ...styles.td,
                          textAlign: "center",
                          fontFamily: "var(--mono)",
                          color: isBest ? "var(--success)" : val == null ? "var(--text-dim)" : "var(--text)",
                          fontWeight: isBest ? 600 : 400,
                        }}
                      >
                        {val != null ? (fmt ? fmt(val) : String(val)) : "—"}
                      </td>
                    );
                  })}
                  <td
                    style={{
                      ...styles.td,
                      textAlign: "center",
                      fontFamily: "var(--mono)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {diff ? (METRIC_FMT[key] ? METRIC_FMT[key](diff.diff) : diff.diff.toFixed(4)) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 14px",
    borderBottom: "1px solid var(--border)",
  },
  closeBtn: {
    padding: "4px 8px",
    borderRadius: 4,
    border: "1px solid var(--border)",
    background: "transparent",
    color: "var(--text-secondary)",
    fontSize: 12,
    cursor: "pointer",
  },
  chartPanel: {
    padding: "12px 14px",
    background: "var(--bg-secondary)",
    borderBottom: "1px solid var(--border)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 12,
  },
  th: {
    textAlign: "left",
    padding: "8px 10px",
    color: "var(--text-secondary)",
    fontWeight: 600,
    borderBottom: "1px solid var(--border)",
    position: "sticky" as const,
    top: 0,
    background: "var(--bg)",
    fontSize: 11,
  },
  td: {
    padding: "6px 10px",
    borderBottom: "1px solid var(--border-light)",
  },
};
