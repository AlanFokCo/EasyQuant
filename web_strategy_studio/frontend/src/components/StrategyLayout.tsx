import type { editor } from "monaco-editor";
import { MarkerSeverity } from "monaco-editor";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiJson, ApiError, resolveArtifactUrl } from "../api/client";
import { useRunStream } from "../hooks/useRunStream";
import { useEditorStore } from "../store/editorStore";
import { useTheme, monacoThemeName } from "../hooks/useTheme";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { AppShell } from "./AppShell";
import { CommandPalette } from "./CommandPalette";
import { DataManagementPanel } from "./DataManagementPanel";
import { EditorToolbar } from "./EditorToolbar";
import { LogConsole } from "./LogConsole";
import { MetricsComparison } from "./MetricsComparison";
import { MonacoStrategyEditor } from "./MonacoStrategyEditor";
import { ReportLinkModal } from "./ReportLinkModal";
import { RunsHistoryPanel } from "./RunsHistoryPanel";
import { RunProgressBar } from "./RunProgressBar";
import { ToastContainer } from "./ToastNotification";
import { StockPicker } from "./StockPicker";

type ParamDef = { name: string; type: string; default: string | number | boolean };

type LintResponse = {
  ok: boolean;
  syntax_errors: { line: number; col: number; message: string; severity: string }[];
  lint_issues: { code: string; line: number; col: number; message: string; severity: string }[];
  security_notes: { code: string; line: number; message: string }[];
  params?: ParamDef[];
};

type StrategyDetail = {
  id: string;
  name: string;
  source_code: string;
  version: number;
};

const LS_KEY = "eq_studio_strategy_id";

function buildMarkers(lint: LintResponse | null): editor.IMarkerData[] {
  if (!lint) return [];
  const m: editor.IMarkerData[] = [];
  for (const s of lint.syntax_errors) {
    m.push({
      severity: MarkerSeverity.Error,
      message: s.message,
      startLineNumber: s.line,
      startColumn: Math.max(1, s.col),
      endLineNumber: s.line,
      endColumn: Math.max(s.col + 1, s.col + 2),
    });
  }
  for (const i of lint.lint_issues) {
    m.push({
      severity: MarkerSeverity.Warning,
      message: `${i.code}: ${i.message}`,
      startLineNumber: i.line,
      startColumn: Math.max(1, i.col),
      endLineNumber: i.line,
      endColumn: i.col + 8,
    });
  }
  for (const n of lint.security_notes) {
    m.push({
      severity: MarkerSeverity.Warning,
      message: `${n.code}: ${n.message}`,
      startLineNumber: n.line,
      startColumn: 1,
      endLineNumber: n.line,
      endColumn: 40,
    });
  }
  return m;
}

export function StrategyLayout() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [strategyId, setStrategyId] = useState<string | null>(() => localStorage.getItem(LS_KEY));
  const [source, setSource] = useState("");
  const [fontSize, setFontSize] = useState(14);
  const [lint, setLint] = useState<LintResponse | null>(null);
  const [lintParams, setLintParams] = useState<ParamDef[]>([]);
  const [paramValues, setParamValues] = useState<Record<string, string | number | boolean>>({});
  const [params, setParams] = useState({
    start_date: "2024-01-01",
    end_date: "2024-03-31",
    starting_cash: 100000,
    benchmark: "000300.XSHG",
    universe: [] as string[],
    use_local: true,
  });
  const setDirty = useEditorStore((s) => s.setDirty);
  const runIdStore = useEditorStore((s) => s.runId);
  const setRunId = useEditorStore((s) => s.setRunId);
  const showHistory = useEditorStore((s) => s.showHistory);
  const showCompare = useEditorStore((s) => s.showCompare);
  const showData = useEditorStore((s) => s.showData);
  const addToast = useEditorStore((s) => s.addToast);
  const setShowHistory = useEditorStore((s) => s.setShowHistory);
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const setShowData = useEditorStore((s) => s.setShowData);
  const setCommandPaletteOpen = useEditorStore((s) => s.setCommandPaletteOpen);
  const commandPaletteOpen = useEditorStore((s) => s.commandPaletteOpen);
  const { logs, progress, stage, artifacts, doneStatus, doneError, clearLogs } = useRunStream(runIdStore);
  const [reportOpen, setReportOpen] = useState(false);

  // Theme — apply data-theme + get resolved Monaco theme name
  const { resolvedTheme } = useTheme();
  const monacoTheme = monacoThemeName(resolvedTheme);

  const markers = useMemo(() => buildMarkers(lint), [lint]);

  const bootRef = useRef(false);
  const hydrated = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const bootstrap = useMutation({
    mutationFn: async () => {
      const tpl = await apiJson<{ source_code: string }>("/api/v1/strategies/_new/template");
      const created = await apiJson<{ id: string }>("/api/v1/strategies", {
        method: "POST",
        body: JSON.stringify({
          name: "我的策略",
          description: "Web Studio 自动创建",
          source_code: tpl.source_code,
        }),
      });
      localStorage.setItem(LS_KEY, created.id);
      return created.id;
    },
    onSuccess: (id) => {
      setStrategyId(id);
      qc.invalidateQueries({ queryKey: ["strategy", id] });
    },
  });

  const { data: strategy, error } = useQuery({
    queryKey: ["strategy", strategyId],
    enabled: !!strategyId,
    queryFn: () => apiJson<StrategyDetail>(`/api/v1/strategies/${strategyId}`),
    retry: false,
  });

  // HIGH-19: Track server-side version to detect concurrent edits
  const [serverVersion, setServerVersion] = useState<number | null>(strategy?.version ?? null);

  // If the stored strategy ID no longer exists (e.g. database was reset),
  // clear it so the bootstrap effect creates a fresh strategy.
  useEffect(() => {
    if (error && strategyId) {
      localStorage.removeItem(LS_KEY);
      bootRef.current = false; // allow bootstrap to re-run
      setStrategyId(null);
    }
  }, [error, strategyId]);

  useEffect(() => {
    hydrated.current = false;
  }, [strategyId]);

  useEffect(() => {
    if (!strategy || hydrated.current) return;
    setSource(strategy.source_code);
    setServerVersion(strategy.version);
    hydrated.current = true;
  }, [strategy]);

  useEffect(() => {
    if (strategyId) return;
    if (bootRef.current) return;
    bootRef.current = true;
    bootstrap.mutate();
  }, [strategyId, bootstrap]);

  const debouncedSave = useCallback(
    (code: string) => {
      // Guard early: if no strategy is loaded yet, there's nothing to save.
      if (!strategyId) return;
      setDirty(true);
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(async () => {
        saveTimerRef.current = null;
        try {
          // HIGH-19: Pass expected_version so the server can detect concurrent edits.
          const patchBody: Record<string, unknown> = { source_code: code };
          if (serverVersion !== null) {
            patchBody.expected_version = serverVersion;
          }
          const result = await apiJson<StrategyDetail>(`/api/v1/strategies/${strategyId}`, {
            method: "PATCH",
            body: JSON.stringify(patchBody),
          });
          setDirty(false);
          setServerVersion(result.version);
          qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
        } catch (e) {
          // HIGH-19: 409 VERSION_CONFLICT — ask the user what to do.
          if (e instanceof ApiError && e.code === "VERSION_CONFLICT") {
            const overwrite = window.confirm(
              "远端有改动，你的保存会覆盖它。\n\n点「确定」强制覆盖，点「取消」放弃本次保存并刷新。"
            );
            if (overwrite) {
              // Force-write without expected_version
              try {
                const result = await apiJson<StrategyDetail>(`/api/v1/strategies/${strategyId}`, {
                  method: "PATCH",
                  body: JSON.stringify({ source_code: code }),
                });
                setDirty(false);
                setServerVersion(result.version);
                qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
              } catch (e2) {
                addToast("error", e2 instanceof Error ? e2.message : "强制保存失败");
              }
            } else {
              setDirty(false);
              qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
            }
          } else {
            addToast("error", e instanceof Error ? e.message : "保存失败");
          }
        }
      }, 400);
    },
    [strategyId, serverVersion, qc, setDirty, addToast],
  );

  // Clear any pending debounced-save when strategyId changes to prevent
  // a late PATCH firing against the wrong strategy (B11).
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [strategyId]);

  const onCodeChange = useCallback(
    (v: string) => {
      setSource(v);
      debouncedSave(v);
    },
    [debouncedSave]
  );

  const lintMut = useMutation({
    mutationFn: async () => {
      const body: LintResponse = await apiJson("/api/v1/lint", {
        method: "POST",
        body: JSON.stringify({ source_code: source, profile: "fast" }),
      });
      return body;
    },
    onSuccess: (r) => {
      setLint(r);
      // HIGH-21: Extract # @param declarations for dynamic param panel
      if (r.params && r.params.length > 0) {
        setLintParams(r.params);
        const defaults: Record<string, string | number | boolean> = {};
        for (const p of r.params) {
          defaults[p.name] = p.default;
        }
        setParamValues((prev) => ({ ...defaults, ...prev }));
      } else {
        setLintParams([]);
      }
      addToast(r.ok ? "success" : "error", r.ok ? "代码检查通过" : "代码检查存在问题");
    },
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "代码检查失败");
    },
  });

  const formatMut = useMutation({
    mutationFn: async () => {
      const r = await apiJson<{ formatted_source: string; ok: boolean }>("/api/v1/format", {
        method: "POST",
        body: JSON.stringify({ source_code: source }),
      });
      return r;
    },
    onSuccess: (r) => {
      if (r.ok) setSource(r.formatted_source);
    },
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "格式化失败");
    },
  });

  const runMut = useMutation({
    mutationFn: async () => {
      if (!strategyId) throw new Error("no strategy");
      setReportOpen(false);
      clearLogs();
      const res = await apiJson<{ run_id: string }>("/api/v1/runs", {
        method: "POST",
        body: JSON.stringify({
          strategy_id: strategyId,
          source_code: source,
          params: {
            ...params,
            // Map universe → securities (backend field name); omit if empty
            securities: params.universe.length > 0 ? params.universe : undefined,
            universe: undefined,
            strategy_params: lintParams.length > 0 ? { ...paramValues } : undefined,
          },
        }),
      });
      return res.run_id;
    },
    onSuccess: (rid) => {
      setRunId(rid);
      addToast("info", "回测已开始运行");
    },
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "启动回测失败");
    },
  });

  const running = !!runIdStore && doneStatus === null;

  // Toast on completion
  useEffect(() => {
    if (doneStatus === "succeeded") {
      addToast("success", "回测已完成，可在历史记录中查看报告");
    } else if (doneStatus === "failed") {
      addToast("error", "回测失败，请查看下方日志");
    }
  }, [doneStatus, addToast]);

  const reportOpenUrl = useMemo(() => {
    const fromApi = resolveArtifactUrl(artifacts?.html_report_url ?? undefined);
    if (fromApi) return fromApi;
    if (runIdStore) return resolveArtifactUrl(`/api/v1/reports/${runIdStore}/report.html`);
    return undefined;
  }, [artifacts?.html_report_url, runIdStore]);

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  useKeyboardShortcuts({
    onSave: () => lintMut.mutate(),
    onRun: () => { if (!running) runMut.mutate(); },
    onFormat: () => formatMut.mutate(),
    onTogglePalette: () => setCommandPaletteOpen(!commandPaletteOpen),
    onShowHistory: () => { setShowHistory(true); setShowCompare(false); },
    onShowCompare: () => { setShowCompare(true); setShowHistory(false); },
    onEscape: () => {
      if (commandPaletteOpen) setCommandPaletteOpen(false);
      else if (reportOpen) setReportOpen(false);
      else if (showHistory) setShowHistory(false);
      else if (showCompare) setShowCompare(false);
      else if (showData) setShowData(false);
    },
  });

  // Determine right panel content
  const rightPanel = (() => {
    if (showHistory) {
      return <RunsHistoryPanel strategyId={strategyId} />;
    }
    if (showCompare) {
      return <MetricsComparison />;
    }
    if (showData) {
      return <DataManagementPanel />;
    }
    return (
      <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10, overflow: "auto", flex: 1 }}>
        {/* Run & Lint buttons */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            aria-label="运行代码检查 (Cmd+S)"
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--primary)",
              background: "transparent",
              color: "var(--primary)",
              fontWeight: 500,
              fontSize: 13,
              cursor: "pointer",
              transition: "background var(--motion-fast)",
            }}
            onClick={() => lintMut.mutate()}
          >
            代码检查
          </button>
          <button
            type="button"
            aria-label={running ? "回测运行中" : "运行回测 (Cmd+Enter)"}
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: running ? "var(--text-dim)" : "var(--primary)",
              color: "#fff",
              fontWeight: 500,
              fontSize: 13,
              cursor: running || !strategyId ? "not-allowed" : "pointer",
              opacity: !strategyId ? 0.6 : 1,
              transition: "background var(--motion-fast)",
            }}
            onClick={() => runMut.mutate()}
            disabled={!strategyId || running}
          >
            {running ? "运行中…" : "运行回测"}
          </button>
        </div>

        {/* Backtest Params */}
        <fieldset
          style={{
            background: "var(--bg-secondary)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border)",
            padding: 10,
            fontSize: 12,
          }}
        >
          <legend style={{ fontWeight: 600, padding: "0 4px", fontSize: 12 }}>回测参数</legend>

          {/* HIGH-21: Date pickers */}
          <label style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
            开始日期
            <input
              type="date"
              aria-label="开始日期"
              style={{
                width: "100%",
                marginTop: 2,
                padding: 4,
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text)",
                fontSize: 12,
              }}
              value={params.start_date}
              onChange={(e) => setParams((p) => ({ ...p, start_date: e.target.value }))}
            />
          </label>
          <label style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
            结束日期
            <input
              type="date"
              aria-label="结束日期"
              style={{
                width: "100%",
                marginTop: 2,
                padding: 4,
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text)",
                fontSize: 12,
              }}
              value={params.end_date}
              onChange={(e) => setParams((p) => ({ ...p, end_date: e.target.value }))}
            />
          </label>

          {/* PR-1: Benchmark picker (single) */}
          <label style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
            基准指数
            <StockPicker
              value={params.benchmark}
              onChange={(code) => setParams((p) => ({ ...p, benchmark: code }))}
              placeholder="默认 000300.XSHG（沪深 300）"
            />
          </label>

          {/* PR-1: Universe (multi-stock pool) */}
          <div style={{ marginBottom: 6 }}>
            <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>
              股票池（可选）
            </div>
            {params.universe.length === 0 && (
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 4 }}>
                留空表示使用策略源码里的 # @param securities / @param security
              </div>
            )}
            {params.universe.map((code, idx) => (
              <div key={idx} style={{ display: "flex", gap: 4, alignItems: "center", marginBottom: 4 }}>
                <div style={{ flex: 1 }}>
                  <StockPicker
                    value={code}
                    onChange={(c) =>
                      setParams((p) => {
                        const u = [...p.universe];
                        u[idx] = c;
                        return { ...p, universe: u };
                      })
                    }
                    placeholder="搜索股票代码/名称"
                  />
                </div>
                <button
                  type="button"
                  aria-label={`删除第 ${idx + 1} 只股票`}
                  onClick={() =>
                    setParams((p) => ({ ...p, universe: p.universe.filter((_, i) => i !== idx) }))
                  }
                  style={{
                    flexShrink: 0,
                    padding: "2px 6px",
                    background: "transparent",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-dim)",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setParams((p) => ({ ...p, universe: [...p.universe, ""] }))}
              style={{
                padding: "2px 8px",
                background: "transparent",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text-secondary)",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              + 添加股票
            </button>
          </div>

          <label style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
            starting_cash
            <input
              type="number"
              aria-label="初始资金"
              style={{
                width: "100%",
                marginTop: 2,
                padding: 4,
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text)",
                fontSize: 12,
              }}
              value={params.starting_cash}
              onChange={(e) => setParams((p) => ({ ...p, starting_cash: Number(e.target.value) }))}
            />
          </label>

          {/* HIGH-21: Dynamic @param inputs */}
          {lintParams.length > 0 && (
            <>
              <div style={{ borderTop: "1px solid var(--border)", margin: "8px 0" }} />
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 4 }}>策略参数（# @param）</div>
              {lintParams.map((p) => (
                <label key={p.name} style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
                  {p.name}
                  {p.type === "checkbox" ? (
                    <input
                      type="checkbox"
                      checked={Boolean(paramValues[p.name])}
                      onChange={(e) => setParamValues((v) => ({ ...v, [p.name]: e.target.checked }))}
                      style={{ marginLeft: 6 }}
                    />
                  ) : (
                    <input
                      type={p.type === "number" ? "number" : "text"}
                      aria-label={p.name}
                      style={{
                        width: "100%",
                        marginTop: 2,
                        padding: 4,
                        background: "var(--bg)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-sm)",
                        color: "var(--text)",
                        fontSize: 12,
                      }}
                      value={String(paramValues[p.name] ?? p.default)}
                      onChange={(e) => setParamValues((v) => ({ ...v, [p.name]: p.type === "number" ? Number(e.target.value) : e.target.value }))}
                    />
                  )}
                </label>
              ))}
            </>
          )}

          <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
            <input
              type="checkbox"
              aria-label="使用本地 CSV 数据"
              checked={params.use_local}
              onChange={(e) => setParams((p) => ({ ...p, use_local: e.target.checked }))}
            />
            <span>use_local（本地 CSV）</span>
          </label>
        </fieldset>

        <RunProgressBar progress={progress} stage={stage} running={running} runId={runIdStore} />

        {/* Success card */}
        {doneStatus === "succeeded" && (runIdStore || artifacts?.html_report_url) ? (
          <div
            role="status"
            aria-live="polite"
            style={{
              background: "var(--bg-secondary)",
              borderRadius: "var(--radius-md)",
              border: "1px solid rgba(63,185,80,0.35)",
              padding: 12,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, color: "var(--state-success)" }}>
              回测已完成
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                type="button"
                aria-label="在浮层中查看 HTML 报告"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "var(--primary)",
                  color: "#fff",
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: "pointer",
                }}
                onClick={() => setReportOpen(true)}
              >
                查看 HTML 报告
              </button>
              {/* Open in workspace (standalone route) */}
              {runIdStore && (
                <button
                  type="button"
                  aria-label="在独立页面打开报告"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border)",
                    background: "transparent",
                    color: "var(--text-secondary)",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                  onClick={() => navigate(`/runs/${runIdStore}/report`)}
                >
                  在工作台打开
                </button>
              )}
              {reportOpenUrl ? (
                <button
                  type="button"
                  aria-label="在新标签页打开报告"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border)",
                    background: "transparent",
                    color: "var(--text-secondary)",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                  onClick={() => {
                    window.open(`/runs/${runIdStore}/report`, "_blank", "noopener,noreferrer");
                  }}
                >
                  新标签打开报告
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Failure card */}
        {doneStatus === "failed" ? (
          <div
            role="alert"
            style={{
              fontSize: 12,
              color: "var(--state-error)",
              padding: 10,
              background: "var(--bg-secondary)",
              borderRadius: "var(--radius-md)",
              border: "1px solid rgba(248,81,73,0.25)",
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              回测失败
              {doneError && ` (${doneError.code})`}
            </div>
            {doneError && (
              <div style={{ color: "var(--text)", marginBottom: 4 }}>
                {doneError.message}
              </div>
            )}
            <div>请查看下方日志中的详细报错信息。</div>
          </div>
        ) : null}

        <LogConsole
          lines={logs}
          onClear={clearLogs}
          onDownload={() => {
            const blob = new Blob([logs.map((l) => `[${l.stream}] ${l.line}`).join("\n")], {
              type: "text/plain;charset=utf-8",
            });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "studio-run.log";
            a.click();
            URL.revokeObjectURL(a.href);
          }}
        />

        {lint && (
          <div
            role="status"
            style={{ fontSize: 11, color: lint.ok ? "var(--state-success)" : "var(--state-error)" }}
          >
            检查: {lint.ok ? "通过" : "存在问题（见编辑器波浪线与日志）"}
          </div>
        )}
      </div>
    );
  })();

  // Editor panel (left side of split)
  const editorPanel = (
    <>
      <EditorToolbar
        fontSize={fontSize}
        onFontDelta={(d) => setFontSize((s) => Math.min(28, Math.max(10, s + d)))}
        onFormat={() => formatMut.mutate()}
        onRunBacktest={() => runMut.mutate()}
        running={running}
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
      />
      <div style={{ flex: 1, minHeight: 0 }}>
        <MonacoStrategyEditor
          value={source}
          onChange={onCodeChange}
          markers={markers}
          fontSize={fontSize}
          monacoTheme={monacoTheme}
        />
      </div>
    </>
  );

  return (
    <>
      <AppShell editor={editorPanel} rightPane={rightPanel} />

      <ReportLinkModal
        open={reportOpen}
        htmlUrl={artifacts?.html_report_url ?? undefined}
        runId={runIdStore}
        onClose={() => setReportOpen(false)}
      />

      <CommandPalette
        onRun={() => { if (!running) runMut.mutate(); }}
        onFormat={() => formatMut.mutate()}
        onClearLogs={clearLogs}
      />

      <ToastContainer />
    </>
  );
}
