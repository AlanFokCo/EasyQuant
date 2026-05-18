import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { fetchRunsList, RunListItem } from "../api/client";
import { useEditorStore } from "../store/editorStore";
import { ReportLinkModal } from "./ReportLinkModal";

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  succeeded: { bg: "var(--success-bg)", color: "var(--success)", label: "成功" },
  failed: { bg: "var(--error-bg)", color: "var(--error)", label: "失败" },
  running: { bg: "var(--primary-bg)", color: "var(--primary)", label: "运行中" },
  queued: { bg: "var(--warning-bg)", color: "var(--warning)", label: "排队中" },
  cancelled: { bg: "rgba(139,148,158,0.1)", color: "var(--text-secondary)", label: "已取消" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RunsHistoryPanel({ strategyId }: { strategyId: string | null }) {
  const setShowHistory = useEditorStore((s) => s.setShowHistory);
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const compareIds = useEditorStore((s) => s.compareIds);
  const setCompareIds = useEditorStore((s) => s.setCompareIds);
  const setRunId = useEditorStore((s) => s.setRunId);
  const currentRunId = useEditorStore((s) => s.runId);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["runs", strategyId],
    queryFn: () => fetchRunsList(strategyId ?? undefined),
    refetchInterval: 10_000,
  });

  const runs = useMemo(() => data?.runs ?? [], [data]);

  return (
    <>
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
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>回测历史</h3>
          <div style={{ display: "flex", gap: 6 }}>
            {compareIds.length >= 2 && (
              <button
                type="button"
                style={{
                  padding: "4px 10px",
                  borderRadius: 4,
                  border: "1px solid var(--primary)",
                  background: "var(--primary-bg)",
                  color: "var(--primary)",
                  fontSize: 12,
                  fontWeight: 500,
                }}
                onClick={() => setShowCompare(true)}
              >
                对比 ({compareIds.length})
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowHistory(false)}
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
        </div>

        {/* List */}
        <div style={{ flex: 1, overflow: "auto", padding: "4px 0" }}>
          {isLoading && (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
              加载中…
            </div>
          )}
          {!isLoading && runs.length === 0 && (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
              暂无回测记录
            </div>
          )}
          {runs.map((run) => (
            <RunRow
              key={run.run_id}
              run={run}
              selected={compareIds.includes(run.run_id)}
              isAttached={currentRunId === run.run_id}
              onToggleCompare={() => {
                setCompareIds(
                  compareIds.includes(run.run_id)
                    ? compareIds.filter((id) => id !== run.run_id)
                    : compareIds.length < 5
                      ? [...compareIds, run.run_id]
                      : compareIds
                );
              }}
              onOpenReport={() => setSelectedRunId(run.run_id)}
              onReattach={() => setRunId(run.run_id)}
            />
          ))}
        </div>
      </div>

      <ReportLinkModal
        open={!!selectedRunId}
        htmlUrl={selectedRunId ? `/api/v1/reports/${selectedRunId}/report.html` : null}
        runId={selectedRunId}
        onClose={() => setSelectedRunId(null)}
      />
    </>
  );
}

function RunRow({
  run,
  selected,
  isAttached,
  onToggleCompare,
  onOpenReport,
  onReattach,
}: {
  run: RunListItem;
  selected: boolean;
  isAttached: boolean;
  onToggleCompare: () => void;
  onOpenReport: () => void;
  onReattach: () => void;
}) {
  const badge = STATUS_BADGE[run.status] ?? STATUS_BADGE.queued;
  const pct = Math.round(run.progress * 100);
  const canReattach = (run.status === "queued" || run.status === "running") && !isAttached;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 4,
        padding: "8px 14px",
        borderBottom: "1px solid var(--border-light)",
        background: selected ? "var(--primary-bg)" : "transparent",
        cursor: "pointer",
        transition: "background 0.15s",
      }}
      onClick={run.status === "succeeded" ? onOpenReport : undefined}
      onMouseEnter={(e) => {
        if (!selected) (e.currentTarget.style.background = "var(--card-hover)");
      }}
      onMouseLeave={(e) => {
        if (!selected) (e.currentTarget.style.background = "transparent");
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            fontSize: 11,
            fontFamily: "var(--mono)",
            color: "var(--text-dim)",
            maxWidth: 120,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {run.run_id.slice(0, 16)}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {run.queue_position != null && (
            <span style={{ fontSize: 10, color: "var(--warning)", fontFamily: "var(--mono)" }}>
              #{run.queue_position}
            </span>
          )}
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              padding: "2px 8px",
              borderRadius: 10,
              background: badge.bg,
              color: badge.color,
            }}
          >
            {badge.label}
          </span>
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          {run.strategy_name ?? "未命名"}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{formatDate(run.started_at)}</span>
      </div>
      {run.status === "running" && (
        <div style={{ height: 2, borderRadius: 1, background: "var(--border-light)", overflow: "hidden" }}>
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: "var(--primary)",
              transition: "width 0.3s",
            }}
          />
        </div>
      )}
      {run.status === "failed" && run.error_message && (
        <div
          style={{
            fontSize: 11,
            color: "var(--error)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {run.error_message}
        </div>
      )}
      {/* Action buttons */}
      <div style={{ display: "flex", gap: 6 }}>
        {/* B7: Reattach button for queued/running runs */}
        {canReattach && (
          <button
            type="button"
            style={{
              flex: 1,
              padding: "4px 8px",
              borderRadius: 4,
              border: "1px solid var(--primary)",
              background: "var(--primary-bg)",
              color: "var(--primary)",
              fontSize: 11,
              fontWeight: 500,
            }}
            onClick={(e) => {
              e.stopPropagation();
              onReattach();
            }}
          >
            重新附加
          </button>
        )}
        {isAttached && (run.status === "queued" || run.status === "running") && (
          <span style={{ flex: 1, textAlign: "center", fontSize: 11, color: "var(--primary)", padding: "4px 0" }}>
            ✓ 已附加
          </span>
        )}
        {run.status === "succeeded" && (
          <>
            <button
              type="button"
              style={{
                flex: 1,
                padding: "4px 8px",
                borderRadius: 4,
                border: "none",
                background: "var(--primary)",
                color: "#fff",
                fontSize: 11,
                fontWeight: 500,
              }}
              onClick={(e) => {
                e.stopPropagation();
                onOpenReport();
              }}
            >
              查看报告
            </button>
            <button
              type="button"
              style={{
                padding: "4px 8px",
                borderRadius: 4,
                border: "1px solid var(--border)",
                background: "transparent",
                color: selected ? "var(--primary)" : "var(--text-dim)",
                fontSize: 11,
              }}
              onClick={(e) => {
                e.stopPropagation();
                onToggleCompare();
              }}
            >
              {selected ? "✓ 已选" : "对比"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
