import type { editor } from "monaco-editor";
import { MarkerSeverity } from "monaco-editor";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiJson, resolveArtifactUrl } from "../api/client";
import { useRunStream } from "../hooks/useRunStream";
import { useEditorStore } from "../store/editorStore";
import { EditorToolbar } from "./EditorToolbar";
import { LogConsole } from "./LogConsole";
import { MonacoStrategyEditor } from "./MonacoStrategyEditor";
import { ReportLinkModal } from "./ReportLinkModal";
import { RunProgressBar } from "./RunProgressBar";

type LintResponse = {
  ok: boolean;
  syntax_errors: { line: number; col: number; message: string; severity: string }[];
  lint_issues: { code: string; line: number; col: number; message: string; severity: string }[];
  security_notes: { code: string; line: number; message: string }[];
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
  const [strategyId, setStrategyId] = useState<string | null>(() => localStorage.getItem(LS_KEY));
  const [source, setSource] = useState("");
  const [fontSize, setFontSize] = useState(14);
  const [lint, setLint] = useState<LintResponse | null>(null);
  const [params, setParams] = useState({
    start_date: "2024-01-01",
    end_date: "2024-03-31",
    starting_cash: 100000,
    benchmark: "000300.XSHG",
    use_local: true,
  });
  const setDirty = useEditorStore((s) => s.setDirty);
  const runIdStore = useEditorStore((s) => s.runId);
  const setRunId = useEditorStore((s) => s.setRunId);
  const { logs, progress, stage, artifacts, doneStatus, clearLogs } = useRunStream(runIdStore);
  const [reportOpen, setReportOpen] = useState(false);

  const markers = useMemo(() => buildMarkers(lint), [lint]);

  const bootRef = useRef(false);
  const hydrated = useRef(false);

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

  const { data: strategy } = useQuery({
    queryKey: ["strategy", strategyId],
    enabled: !!strategyId,
    queryFn: () => apiJson<StrategyDetail>(`/api/v1/strategies/${strategyId}`),
  });

  useEffect(() => {
    hydrated.current = false;
  }, [strategyId]);

  useEffect(() => {
    if (!strategy || hydrated.current) return;
    setSource(strategy.source_code);
    hydrated.current = true;
  }, [strategy]);

  useEffect(() => {
    if (strategyId) return;
    if (bootRef.current) return;
    bootRef.current = true;
    bootstrap.mutate();
  }, [strategyId, bootstrap]);

  const debouncedSave = useMemo(() => {
    let t: ReturnType<typeof setTimeout> | null = null;
    return (code: string) => {
      setDirty(true);
      if (t) clearTimeout(t);
      t = setTimeout(async () => {
        if (!strategyId) return;
        try {
          await apiJson(`/api/v1/strategies/${strategyId}`, {
            method: "PATCH",
            body: JSON.stringify({ source_code: code }),
          });
          setDirty(false);
          qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
        } catch {
          /* ignore */
        }
      }, 400);
    };
  }, [strategyId, qc, setDirty]);

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
    onSuccess: (r) => setLint(r),
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
          params,
        }),
      });
      return res.run_id;
    },
    onSuccess: (rid) => {
      setRunId(rid);
    },
  });

  useEffect(() => {
    if (doneStatus === "succeeded" && (artifacts?.html_report_url || runIdStore)) {
      setReportOpen(true);
    }
  }, [doneStatus, artifacts, runIdStore]);

  const running = !!runIdStore && doneStatus === null;

  const reportOpenUrl = useMemo(() => {
    const fromApi = resolveArtifactUrl(artifacts?.html_report_url ?? undefined);
    if (fromApi) return fromApi;
    if (runIdStore) return resolveArtifactUrl(`/static/reports/${runIdStore}/report.html`);
    return undefined;
  }, [artifacts?.html_report_url, runIdStore]);

  return (
    <div style={{ display: "flex", flexDirection: "row", height: "100vh", overflow: "hidden" }}>
      <div style={{ flex: "0 0 70%", minWidth: 0, display: "flex", flexDirection: "column" }}>
        <EditorToolbar
          fontSize={fontSize}
          onFontDelta={(d) => setFontSize((s) => Math.min(28, Math.max(10, s + d)))}
          onFormat={() => formatMut.mutate()}
        />
        <div style={{ flex: 1, minHeight: 0 }}>
          <MonacoStrategyEditor value={source} onChange={onCodeChange} markers={markers} fontSize={fontSize} />
        </div>
      </div>
      <div
        style={{
          flex: "0 0 30%",
          minWidth: 280,
          borderLeft: "1px solid #e8e8e8",
          padding: 12,
          display: "flex",
          flexDirection: "column",
          gap: 10,
          background: "var(--bg)",
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: 4,
              border: "1px solid var(--primary)",
              background: "#fff",
              color: "var(--primary)",
              fontWeight: 500,
            }}
            onClick={() => lintMut.mutate()}
          >
            代码检查
          </button>
          <button
            type="button"
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: 4,
              border: "none",
              background: "var(--primary)",
              color: "#fff",
              fontWeight: 500,
            }}
            onClick={() => runMut.mutate()}
            disabled={!strategyId}
          >
            运行回测
          </button>
        </div>

        <div
          style={{
            background: "var(--card)",
            borderRadius: 4,
            boxShadow: "var(--shadow-card)",
            padding: 10,
            fontSize: 12,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 8 }}>回测参数</div>
          {(["start_date", "end_date", "benchmark"] as const).map((k) => (
            <label key={k} style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
              {k}
              <input
                style={{ width: "100%", marginTop: 2, padding: 4 }}
                value={String((params as Record<string, unknown>)[k])}
                onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
              />
            </label>
          ))}
          <label style={{ display: "block", marginBottom: 6, color: "var(--text-secondary)" }}>
            starting_cash
            <input
              type="number"
              style={{ width: "100%", marginTop: 2, padding: 4 }}
              value={params.starting_cash}
              onChange={(e) => setParams((p) => ({ ...p, starting_cash: Number(e.target.value) }))}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
            <input
              type="checkbox"
              checked={params.use_local}
              onChange={(e) => setParams((p) => ({ ...p, use_local: e.target.checked }))}
            />
            <span>use_local（本地 CSV）</span>
          </label>
        </div>

        <RunProgressBar progress={progress} stage={stage} running={running} />

        {doneStatus === "succeeded" && (runIdStore || artifacts?.html_report_url) ? (
          <div
            style={{
              background: "var(--card)",
              borderRadius: 4,
              boxShadow: "var(--shadow-card)",
              padding: 12,
              border: "1px solid rgba(34, 160, 107, 0.35)",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, color: "var(--success-text)" }}>
              回测已完成
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                type="button"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 4,
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
              {reportOpenUrl ? (
                <button
                  type="button"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 4,
                    border: "1px solid var(--primary)",
                    background: "#fff",
                    color: "var(--primary)",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                  onClick={() => window.open(reportOpenUrl, "_blank", "noopener,noreferrer")}
                >
                  新标签打开报告
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {doneStatus === "failed" ? (
          <div
            style={{
              fontSize: 12,
              color: "var(--error-text)",
              padding: 10,
              background: "var(--card)",
              borderRadius: 4,
              border: "1px solid rgba(200, 60, 60, 0.25)",
            }}
          >
            回测未成功，请查看下方日志中的报错信息。
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
          <div style={{ fontSize: 11, color: lint.ok ? "var(--success-text)" : "var(--error-text)" }}>
            检查: {lint.ok ? "通过" : "存在问题（见编辑器波浪线与日志）"}
          </div>
        )}
      </div>

      <ReportLinkModal
        open={reportOpen}
        htmlUrl={artifacts?.html_report_url ?? undefined}
        runId={runIdStore}
        onClose={() => setReportOpen(false)}
      />
    </div>
  );
}
