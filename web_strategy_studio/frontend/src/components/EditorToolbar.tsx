import type { CSSProperties } from "react";

import { useEditorStore } from "../store/editorStore";

type Props = {
  fontSize: number;
  onFontDelta: (d: number) => void;
  onFormat: () => void;
  onRunBacktest: () => void;
  running: boolean;
};

export function EditorToolbar({ fontSize, onFontDelta, onFormat, onRunBacktest, running }: Props) {
  const setShowHistory = useEditorStore((s) => s.setShowHistory);
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const sseConnected = useEditorStore((s) => s.sseConnected);

  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        padding: "6px 12px",
        background: "var(--bg-secondary)",
        borderBottom: "1px solid var(--border)",
        alignItems: "center",
        height: 40,
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginRight: 8 }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.02em" }}>
          EasyQuant
        </span>
      </div>

      {/* Run button */}
      <button
        type="button"
        onClick={onRunBacktest}
        disabled={running}
        style={{
          padding: "4px 16px",
          borderRadius: 4,
          border: "none",
          background: running ? "var(--text-dim)" : "var(--primary)",
          color: "#fff",
          fontWeight: 600,
          fontSize: 12,
          cursor: running ? "not-allowed" : "pointer",
        }}
      >
        {running ? "运行中…" : "运行回测"}
      </button>

      {/* History & Compare */}
      <button type="button" style={ghostBtn} onClick={() => setShowHistory(true)} title="回测历史">
        历史
      </button>
      <button type="button" style={ghostBtn} onClick={() => setShowCompare(true)} title="指标对比">
        对比
      </button>

      <div style={{ flex: 1 }} />

      {/* Connection status */}
      <span
        style={{
          fontSize: 10,
          color: sseConnected ? "var(--success)" : "var(--text-dim)",
          marginRight: 4,
        }}
      >
        {sseConnected ? "●" : "○"}
      </span>

      {/* Format & font */}
      <button type="button" title="格式化" style={iconBtn} onClick={onFormat}>
        格式
      </button>
      <button type="button" title="缩小" style={iconBtn} onClick={() => onFontDelta(-1)}>
        A−
      </button>
      <button type="button" title="放大" style={iconBtn} onClick={() => onFontDelta(1)}>
        A+
      </button>
      <span style={{ fontSize: 11, color: "var(--text-dim)", minWidth: 32 }}>{fontSize}px</span>
    </div>
  );
}

const ghostBtn: CSSProperties = {
  padding: "4px 10px",
  borderRadius: 4,
  border: "1px solid var(--border)",
  background: "transparent",
  color: "var(--text-secondary)",
  fontSize: 12,
};

const iconBtn: CSSProperties = {
  width: 32,
  height: 26,
  border: "1px solid var(--border)",
  borderRadius: 4,
  background: "transparent",
  color: "var(--text-secondary)",
  fontSize: 11,
};
