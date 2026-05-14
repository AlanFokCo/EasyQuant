import type { CSSProperties } from "react";
import { useMemo } from "react";

import { resolveArtifactUrl } from "../api/client";

type Props = {
  open: boolean;
  htmlUrl: string | null | undefined;
  runId?: string | null;
  onClose: () => void;
};

export function ReportLinkModal({ open, htmlUrl, runId, onClose }: Props) {
  const iframeSrc = useMemo(() => {
    const fromApi = resolveArtifactUrl(htmlUrl ?? undefined);
    if (fromApi) return fromApi;
    if (runId) return resolveArtifactUrl(`/static/reports/${runId}/report.html`);
    return undefined;
  }, [htmlUrl, runId]);

  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.65)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      role="dialog"
      aria-modal
    >
      <div
        style={{
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          padding: 16,
          width: "min(100vw - 32px, 1100px)",
          maxHeight: "min(92vh, 900px)",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>回测报告</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {iframeSrc ? (
              <button
                type="button"
                style={ghost}
                onClick={() => window.open(iframeSrc, "_blank", "noopener,noreferrer")}
              >
                新标签打开
              </button>
            ) : null}
            <button type="button" style={ghost} onClick={onClose}>
              关闭
            </button>
          </div>
        </div>
        {iframeSrc ? (
          <iframe
            title="回测 HTML 报告"
            src={iframeSrc}
            sandbox="allow-scripts allow-same-origin allow-downloads"
            style={{
              flex: 1,
              minHeight: 420,
              width: "100%",
              border: "1px solid var(--border)",
              borderRadius: 4,
              background: "#fff",
            }}
          />
        ) : (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
            未拿到报告地址。请确认回测已成功结束。
          </div>
        )}
      </div>
    </div>
  );
}

const ghost: CSSProperties = {
  padding: "6px 14px",
  borderRadius: 4,
  border: "1px solid var(--border)",
  background: "transparent",
  color: "var(--text-secondary)",
  textDecoration: "none",
  fontSize: 13,
  cursor: "pointer",
};
