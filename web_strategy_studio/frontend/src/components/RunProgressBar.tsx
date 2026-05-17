import { useCallback, useState } from "react";
import { Square } from "lucide-react";

import { apiJson } from "../api/client";
import { useEditorStore } from "../store/editorStore";

type Props = {
  progress: number;
  stage: string | null;
  running: boolean;
  runId?: string | null;
};

export function RunProgressBar({ progress, stage, running, runId }: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  const addToast = useEditorStore((s) => s.addToast);
  const [cancelling, setCancelling] = useState(false);

  const handleCancel = useCallback(async () => {
    if (!runId || cancelling) return;
    setCancelling(true);
    try {
      await apiJson(`/api/v1/runs/${runId}/cancel`, { method: "POST" });
      addToast("info", "回测已取消");
    } catch (e) {
      addToast("error", `取消失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setCancelling(false);
    }
  }, [runId, cancelling, addToast]);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          {stage ? `阶段: ${stage}` : running ? "运行中…" : "空闲"}
        </div>
        {running && runId && (
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              fontSize: 11,
              borderRadius: 4,
              border: "1px solid var(--border)",
              background: cancelling ? "var(--bg-tertiary)" : "transparent",
              color: cancelling ? "var(--text-dim)" : "var(--state-error)",
              cursor: cancelling ? "not-allowed" : "pointer",
            }}
            aria-label="取消回测"
          >
            <Square size={12} />
            {cancelling ? "取消中…" : "取消"}
          </button>
        )}
      </div>
      <div
        role="progressbar"
        aria-label="回测进度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        style={{
          height: 6,
          borderRadius: 3,
          background: "var(--border)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: "var(--primary)",
            transition: "width 0.3s ease",
            borderRadius: 3,
          }}
        />
      </div>
      {running && (
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3, textAlign: "right" }}>
          {pct}%
        </div>
      )}
    </div>
  );
}
