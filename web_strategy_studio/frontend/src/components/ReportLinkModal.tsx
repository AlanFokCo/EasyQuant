import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";

import ReportViewer from "./ReportViewer";

type Props = {
  open: boolean;
  htmlUrl: string | null | undefined;
  runId?: string | null;
  onClose: () => void;
};

export function ReportLinkModal({ open, htmlUrl, runId, onClose }: Props) {
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);

  useEffect(() => {
    const ro = new ResizeObserver(() => setViewportWidth(window.innerWidth));
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);

  const isPhone = viewportWidth < 480;

  const jsonUrl = useMemo(() => {
    if (runId) return `/api/v1/reports/${runId}/report.json`;
    // Derive from htmlUrl if available
    if (htmlUrl) return htmlUrl.replace(/\.html$/, ".json");
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
        alignItems: isPhone ? "stretch" : "center",
        justifyContent: isPhone ? "stretch" : "center",
        zIndex: 2000,
      }}
      role="dialog"
      aria-modal
    >
      <div
        style={{
          background: "var(--bg-secondary)",
          border: isPhone ? "none" : "1px solid var(--border)",
          borderRadius: isPhone ? 0 : 8,
          boxShadow: isPhone ? "none" : "0 8px 32px rgba(0,0,0,0.4)",
          padding: isPhone ? 0 : 16,
          width: isPhone ? "100vw" : "min(100vw - 32px, 1100px)",
          height: isPhone ? "100vh" : "auto",
          maxHeight: isPhone ? "100vh" : "min(92vh, 900px)",
          display: "flex",
          flexDirection: "column",
          gap: isPhone ? 8 : 12,
        }}
      >
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: isPhone ? "12px 8px" : 0,
          borderBottom: isPhone ? "1px solid var(--border)" : "none",
        }}>
          <h3 style={{ margin: 0, fontSize: isPhone ? 14 : 15, fontWeight: 600 }}>回测报告</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {runId ? (
              <button
                type="button"
                style={ghost}
                onClick={() => {
                  // Open frontend route; ReportPage uses blob URL to safely pass JWT
                  window.open(`/runs/${runId}/report`, "_blank", "noopener,noreferrer");
                }}
              >
                新标签打开
              </button>
            ) : null}
            <button type="button" style={ghost} onClick={onClose}>
              关闭
            </button>
          </div>
        </div>
        {runId ? (
          <div style={{ flex: 1, minHeight: isPhone ? "calc(100vh - 56px)" : 420, overflow: "auto" }}>
            <ReportViewer runId={runId} jsonUrl={jsonUrl} />
          </div>
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
