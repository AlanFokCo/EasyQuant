/**
 * ReportViewer — native Lightweight Charts rendering for backtest reports.
 * Replaces the iframe approach in ReportLinkModal for full interactivity.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode, LineStyle } from "lightweight-charts";
import type { IChartApi } from "lightweight-charts";

import { resolveArtifactUrl, getToken } from "../api/client";

type ReportData = {
  summary: {
    symbol?: string;
    start_date?: string;
    end_date?: string;
    initial_capital?: number;
    final_value?: number;
    pnl?: number;
    pnl_pct?: number;
    num_trades?: number;
  };
  risk_metrics?: Record<string, number | null>;
  cumulative_returns?: { date: string; total_value: number; cumulative_return: number }[];
  trades?: {
    type: string;
    date: string;
    security: string;
    price: number;
    amount: number;
    commission: number;
  }[];
  // Chart data fields populated by the HTML report generator
  candlestick_data?: { time: string; open: number; high: number; low: number; close: number }[];
  volume_data?: { time: string; value: number; color: string }[];
  ma5_data?: { time: string; value: number }[];
  ma20_data?: { time: string; value: number }[];
  ma60_data?: { time: string; value: number }[];
  rsi_data?: { time: string; value: number }[];
  macd_data?: { time: string; value: number }[];
  macd_signal_data?: { time: string; value: number }[];
  macd_hist_data?: { time: string; value: number; color: string }[];
  bb_upper_data?: { time: string; value: number }[];
  bb_middle_data?: { time: string; value: number }[];
  bb_lower_data?: { time: string; value: number }[];
  support_data?: { time: string; value: number }[];
  resistance_data?: { time: string; value: number }[];
  markers?: { time: string; position: string; color: string; shape: string; text: string }[];
  cum_return_data?: { time: string; value: number }[];
  ret_hs300_data?: { time: string; value: number }[];
  ret_sse_data?: { time: string; value: number }[];
  drawdown_data?: { time: string; value: number }[];
  pnl_bar_data?: { time: string; value: number; color: string }[];
  daily_returns_data?: { time: string; value: number; color: string }[];
  metrics?: Record<string, string | number | null>;
  symbols_list?: string[];
  symbols_data?: Record<string, any>;
};

const CHART_COMMON: any = {
  layout: {
    background: { type: ColorType.Solid, color: "transparent" },
    textColor: "#8c8c8c",
    fontSize: 11,
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif',
  },
  grid: {
    vertLines: { color: "rgba(245,245,245,0.8)" },
    horzLines: { color: "rgba(245,245,245,0.8)" },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: "#d9d9d9", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#8c8c8c" },
    horzLine: { color: "#d9d9d9", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#8c8c8c" },
  },
  timeScale: {
    borderColor: "#e8e8e8",
    barSpacing: 6,
  },
  rightPriceScale: {
    borderColor: "#e8e8e8",
  },
};

export default function ReportViewer({ runId, jsonUrl }: { runId: string; jsonUrl?: string | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<IChartApi[]>([]);
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  // Track viewport width for responsive chart heights
  useEffect(() => {
    const ro = new ResizeObserver(() => setViewportWidth(window.innerWidth));
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);

  const isPhone = viewportWidth < 480;
  const isTablet = viewportWidth >= 480 && viewportWidth < 768;

  // Dynamic chart height based on viewport
  const getChartHeight = useCallback((base: number): number => {
    if (isPhone) return Math.round(base * 0.58);
    if (isTablet) return Math.round(base * 0.75);
    return base;
  }, [isPhone, isTablet]);

  // Export handler — downloads report file via authenticated fetch
  const handleExport = useCallback(async (fmt: string) => {
    setExporting(fmt);
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const url = resolveArtifactUrl(`/api/v1/reports/${runId}/export/${fmt}`);
      if (!url) throw new Error("Invalid export URL");
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `report_${runId}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (e) {
      console.error("[ReportViewer] Export failed:", e);
    } finally {
      setExporting(null);
    }
  }, [runId]);

  // Export report as PNG screenshot of the current chart view
  const handleExportPng = useCallback(() => {
    if (!chartsRef.current.length || !containerRef.current) return;
    setExporting("png");
    try {
      // Use the first chart's canvas for PNG export
      const chartEl = chartsRef.current[0].chartElement();
      const canvas = chartEl.querySelector("canvas");
      if (canvas) {
        const a = document.createElement("a");
        a.href = canvas.toDataURL("image/png");
        a.download = `chart_${runId}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    } catch (e) {
      console.error("[ReportViewer] PNG export failed:", e);
    } finally {
      setExporting(null);
    }
  }, [runId]);

  // Fetch report JSON data
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const apiUrl = jsonUrl || `/api/v1/runs/${runId}/report/data`;
        const url = resolveArtifactUrl(apiUrl);
        if (!url) throw new Error("Invalid report URL");
        const token = getToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(url, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [runId, jsonUrl]);

  // Build charts when data is ready
  useEffect(() => {
    if (!data || !containerRef.current) return;

    // Merge per-symbol data when a symbol is selected
    const effectiveData: ReportData = selectedSymbol && data.symbols_data?.[selectedSymbol]
      ? { ...data, ...data.symbols_data[selectedSymbol] }
      : data;

    // Cleanup previous charts
    chartsRef.current.forEach((c) => c.remove());
    chartsRef.current = [];

    const container = containerRef.current;
    container.innerHTML = "";

    // Symbol switcher
    const symbolsList = data.symbols_list || [];
    if (symbolsList.length > 1) {
      const switcherDiv = document.createElement("div");
      switcherDiv.style.cssText = "margin-bottom:8px;display:flex;align-items:center;gap:8px;";
      const label = document.createElement("span");
      label.textContent = "股票切换:";
      label.style.cssText = "font-size:12px;color:var(--text-dim);";
      switcherDiv.appendChild(label);
      const select = document.createElement("select");
      select.style.cssText = "padding:4px 8px;border-radius:4px;border:1px solid var(--border);background:var(--bg-secondary);color:var(--text);font-size:12px;";
      const allOpt = document.createElement("option");
      allOpt.value = "";
      allOpt.textContent = "总览";
      select.appendChild(allOpt);
      for (const sym of symbolsList) {
        const opt = document.createElement("option");
        opt.value = sym;
        opt.textContent = sym;
        if (sym === selectedSymbol) opt.selected = true;
        select.appendChild(opt);
      }
      select.addEventListener("change", () => {
        setSelectedSymbol(select.value || null);
      });
      switcherDiv.appendChild(select);
      container.appendChild(switcherDiv);
    }

    // Summary cards
    const s = effectiveData.summary || {};
    const summaryDiv = document.createElement("div");
    summaryDiv.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:12px;";
    const cards = [
      ["初始资金", s.initial_capital != null ? `¥${s.initial_capital.toLocaleString()}` : "—"],
      ["期末净值", s.final_value != null ? `¥${s.final_value.toLocaleString()}` : "—"],
      ["总盈亏", s.pnl != null ? `${s.pnl >= 0 ? "+" : ""}${s.pnl.toLocaleString()}` : "—"],
      ["总收益率", s.pnl_pct != null ? `${s.pnl_pct >= 0 ? "+" : ""}${s.pnl_pct.toFixed(2)}%` : "—"],
      ["交易次数", s.num_trades ?? "—"],
    ];
    for (const [label, value] of cards) {
      const card = document.createElement("div");
      card.style.cssText = "background:var(--bg-secondary);border-radius:4px;padding:12px;text-align:center;border:1px solid var(--border);";
      card.innerHTML = `<div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">${label}</div><div style="font-size:16px;font-weight:600;color:var(--text)">${value}</div>`;
      summaryDiv.appendChild(card);
    }
    container.appendChild(summaryDiv);

    // Helper: create chart container + chart
    function makeChart(title: string, baseHeight: number, desc?: string) {
      const height = getChartHeight(baseHeight);
      const panel = document.createElement("div");
      panel.style.cssText = "background:var(--bg-secondary);border-radius:4px;margin-bottom:8px;overflow:hidden;border:1px solid var(--border);";
      const head = document.createElement("div");
      head.style.cssText = "padding:8px 16px;border-bottom:1px solid var(--border);";
      head.innerHTML = `<div style="font-size:13px;font-weight:600;color:var(--text)">${title}</div>${desc ? `<div style="font-size:11px;color:var(--text-dim);margin-top:2px">${desc}</div>` : ""}`;
      panel.appendChild(head);
      const chartDiv = document.createElement("div");
      chartDiv.style.width = "100%";
      chartDiv.style.height = `${height}px`;
      panel.appendChild(chartDiv);
      container.appendChild(panel);

      const chart = createChart(chartDiv, {
        ...CHART_COMMON,
        width: chartDiv.clientWidth,
        height,
      });
      chartsRef.current.push(chart);
      return { chart, chartDiv };
    }

    const candlestick = effectiveData.candlestick_data || [];
    const volume = effectiveData.volume_data || [];
    const markers = effectiveData.markers || [];

    // K-line chart
    if (candlestick.length > 0) {
      const { chart: kChart } = makeChart("K 线图 · 技术指标", 480, "日 K 线含 MA 均线、成交量、买卖信号");
      const cSeries = kChart.addCandlestickSeries({
        upColor: "#f5222d", downColor: "#52c41a",
        borderUpColor: "#f5222d", borderDownColor: "#52c41a",
        wickUpColor: "#f5222d", wickDownColor: "#52c41a",
      } as any);
      cSeries.setData(candlestick);
      if (markers.length) cSeries.setMarkers(markers as any);

      // MA lines
      const addLine = (chartData: { time: string; value: number }[] | undefined, color: string) => {
        if (chartData && chartData.length) {
          const s = kChart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false } as any);
          s.setData(chartData);
        }
      };
      addLine(effectiveData.ma5_data, "#f5222d");
      addLine(effectiveData.ma20_data, "#1890ff");
      addLine(effectiveData.ma60_data, "#722ed1");

      // Bollinger Bands
      if (effectiveData.bb_upper_data?.length) {
        kChart.addLineSeries({ color: "#1890ff", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false } as any).setData(effectiveData.bb_upper_data);
      }
      if (effectiveData.bb_middle_data?.length) {
        kChart.addLineSeries({ color: "#8c8c8c", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false } as any).setData(effectiveData.bb_middle_data);
      }
      if (effectiveData.bb_lower_data?.length) {
        kChart.addLineSeries({ color: "#1890ff", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false } as any).setData(effectiveData.bb_lower_data);
      }
      // Support / Resistance
      if (effectiveData.support_data?.length) {
        kChart.addLineSeries({ color: "#52c41a", lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false } as any).setData(effectiveData.support_data);
      }
      if (effectiveData.resistance_data?.length) {
        kChart.addLineSeries({ color: "#f5222d", lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false } as any).setData(effectiveData.resistance_data);
      }

      // Volume
      if (volume.length) {
        const volS = kChart.addHistogramSeries({
          priceFormat: { type: "volume" },
          priceScaleId: "vol",
        } as any);
        volS.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        volS.setData(volume as any);
      }

      kChart.timeScale().fitContent();
    }

    // Cumulative returns
    const cumRet = effectiveData.cum_return_data || [];
    if (cumRet.length > 0) {
      const { chart: rChart } = makeChart("累计收益率", 300, "策略累计收益与基准对比");
      const stratLine = rChart.addLineSeries({ color: "#f5222d", lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "策略" } as any);
      stratLine.setData(cumRet);
      const hs300 = effectiveData.ret_hs300_data || [];
      if (hs300.length) {
        const hs = rChart.addLineSeries({ color: "#1890ff", lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true, title: "沪深300" } as any);
        hs.setData(hs300);
      }
      const sse = effectiveData.ret_sse_data || [];
      if (sse.length) {
        const ss = rChart.addLineSeries({ color: "#fa8c16", lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true, title: "上证指数" } as any);
        ss.setData(sse);
      }
      rChart.timeScale().fitContent();
    }

    // Drawdown
    const dd = effectiveData.drawdown_data || [];
    if (dd.length > 0) {
      const { chart: ddChart } = makeChart("回撤曲线", 160, "净值相对自身历史峰值的回撤");
      const ddArea = ddChart.addAreaSeries({
        lineColor: "#52c41a", topColor: "rgba(82,196,26,0.12)", bottomColor: "rgba(82,196,26,0)",
        lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
      } as any);
      ddArea.setData(dd);
      ddChart.timeScale().fitContent();
    }

    // Daily P&L
    const pnlBars = effectiveData.pnl_bar_data || [];
    if (pnlBars.length) {
      const { chart: pChart } = makeChart("每日盈亏", 160, "每个交易日资产净值变动额");
      const pHist = pChart.addHistogramSeries({ priceFormat: { type: "volume" } } as any);
      pHist.setData(pnlBars as any);
      pChart.timeScale().fitContent();
    }

    // Daily returns
    const drRaw = effectiveData.daily_returns_data || [];
    if (drRaw.length) {
      const { chart: drChart } = makeChart("每日收益率", 160, "日度收益率分布");
      const drHist = drChart.addHistogramSeries({ priceFormat: { type: "percent" } } as any);
      drHist.setData(drRaw as any);
      drChart.timeScale().fitContent();
    }

    // RSI
    const rsiData = effectiveData.rsi_data || [];
    if (rsiData.length) {
      const { chart: rsiChart } = makeChart("RSI(14)", 160, "超卖区 <30 / 超买区 >70");
      const rsiLine = rsiChart.addLineSeries({ color: "#722ed1", lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false } as any);
      rsiLine.setData(rsiData);
      // Reference lines
      const refTimes = rsiData.map((d) => ({ time: d.time, value: 70 }));
      const ref30 = rsiData.map((d) => ({ time: d.time, value: 30 }));
      const ref50 = rsiData.map((d) => ({ time: d.time, value: 50 }));
      rsiChart.addLineSeries({ color: "rgba(245,34,45,0.4)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false } as any).setData(refTimes);
      rsiChart.addLineSeries({ color: "rgba(82,196,26,0.4)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false } as any).setData(ref30);
      rsiChart.addLineSeries({ color: "rgba(140,140,140,0.3)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false } as any).setData(ref50);
      rsiChart.timeScale().fitContent();
    }

    // MACD
    const macdD = effectiveData.macd_data || [];
    const macdSig = effectiveData.macd_signal_data || [];
    const macdH = effectiveData.macd_hist_data || [];
    if (macdD.length) {
      const { chart: macdChart } = makeChart("MACD(12,26,9)", 160, "MACD 线、Signal 线与柱状图");
      const mHist = macdChart.addHistogramSeries({ priceFormat: { type: "price" } } as any);
      mHist.setData(macdH as any);
      const mL = macdChart.addLineSeries({ color: "#1890ff", lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false } as any);
      mL.setData(macdD);
      const mS = macdChart.addLineSeries({ color: "#fa8c16", lineWidth: 1, priceLineVisible: false, lastValueVisible: false } as any);
      mS.setData(macdSig);
      macdChart.timeScale().fitContent();
    }

    // Sync all charts
    const allCharts = chartsRef.current;
    allCharts.forEach((src) => {
      src.timeScale().subscribeVisibleLogicalRangeChange((range: any) => {
        if (!range) return;
        allCharts.forEach((dst) => {
          if (dst !== src) dst.timeScale().setVisibleLogicalRange(range);
        });
      });
    });

    // Resize observer
    const ro = new ResizeObserver(() => {
      allCharts.forEach((c) => {
        const el = c.chartElement();
        if (el.parentElement) {
          c.applyOptions({ width: el.parentElement.clientWidth });
        }
      });
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chartsRef.current.forEach((c) => c.remove());
      chartsRef.current = [];
    };
  }, [data, selectedSymbol, getChartHeight]);

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
        加载报告数据中…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--state-error)", fontSize: 13 }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Export toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          gap: 6,
          padding: "4px 8px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 11, color: "var(--text-dim)", marginRight: "auto" }}>
          {runId.slice(0, 16)}
        </span>
        <button
          type="button"
          onClick={() => handleExport("html")}
          disabled={!!exporting}
          style={exportBtnStyle}
          title="导出 HTML 报告"
        >
          {exporting === "html" ? "..." : "HTML"}
        </button>
        <button
          type="button"
          onClick={() => handleExport("json")}
          disabled={!!exporting}
          style={exportBtnStyle}
          title="导出 JSON 数据"
        >
          {exporting === "json" ? "..." : "JSON"}
        </button>
        <button
          type="button"
          onClick={handleExportPng}
          disabled={!!exporting}
          style={exportBtnStyle}
          title="导出图表为 PNG"
        >
          {exporting === "png" ? "..." : "PNG"}
        </button>
      </div>
      <div ref={containerRef} style={{ overflow: "auto", padding: "8px 0", flex: 1, minHeight: 0 }} />
    </div>
  );
}

const exportBtnStyle: React.CSSProperties = {
  padding: "3px 10px",
  borderRadius: 4,
  border: "1px solid var(--border)",
  background: "transparent",
  color: "var(--text-secondary)",
  fontSize: 11,
  cursor: "pointer",
  fontFamily: "var(--mono)",
};
