import type { CSSProperties } from "react";

import { useEditorStore } from "../store/editorStore";

type Props = {
  fontSize: number;
  onFontDelta: (d: number) => void;
  onFormat: () => void;
  onRunBacktest: () => void;
  running: boolean;
  onOpenCommandPalette?: () => void;
};

export function EditorToolbar({ fontSize, onFontDelta, onFormat, onRunBacktest, running, onOpenCommandPalette }: Props) {
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
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginRight: 8 }}>
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--primary)"
          strokeWidth="2"
          aria-hidden="true"
        >
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.02em" }}>
          EasyQuant
        </span>
      </div>

      {/* Run button */}
      <button
        type="button"
        aria-label={running ? "回测运行中" : "运行回测 (Cmd+Enter)"}
        onClick={onRunBacktest}
        disabled={running}
        style={{
          padding: "4px 16px",
          borderRadius: "var(--radius-sm)",
          border: "none",
          background: running ? "var(--text-dim)" : "var(--primary)",
          color: "#fff",
          fontWeight: 600,
          fontSize: 12,
          cursor: running ? "not-allowed" : "pointer",
          transition: "background var(--motion-fast)",
        }}
      >
        {running ? "运行中…" : "运行回测"}
      </button>

      {/* History & Compare */}
      <button
        type="button"
        aria-label="查看回测历史 (Cmd+K Cmd+H)"
        style={ghostBtn}
        onClick={() => setShowHistory(true)}
        title="回测历史"
      >
        历史
      </button>
      <button
        type="button"
        aria-label="指标对比 (Cmd+K Cmd+C)"
        style={ghostBtn}
        onClick={() => setShowCompare(true)}
        title="指标对比"
      >
        对比
      </button>

      <div style={{ flex: 1 }} />

      {/* Connection status */}
      <span
        aria-label={sseConnected ? "SSE 已连接" : "SSE 未连接"}
        style={{
          fontSize: 10,
          color: sseConnected ? "var(--state-success)" : "var(--text-dim)",
          marginRight: 4,
        }}
      >
        {sseConnected ? "●" : "○"}
      </span>

      {/* Command palette trigger */}
      {onOpenCommandPalette && (
        <button
          type="button"
          aria-label="打开命令面板 (Cmd+K)"
          title="命令面板 (⌘K)"
          style={iconBtn}
          onClick={onOpenCommandPalette}
        >
          ⌘K
        </button>
      )}

      {/* Format & font */}
      <button type="button" aria-label="格式化代码 (Cmd+Shift+F)" title="格式化" style={iconBtn} onClick={onFormat}>
        格式
      </button>
      <button type="button" aria-label="缩小字号" title="缩小" style={iconBtn} onClick={() => onFontDelta(-1)}>
        A−
      </button>
      <button type="button" aria-label="放大字号" title="放大" style={iconBtn} onClick={() => onFontDelta(1)}>
        A+
      </button>
      <span style={{ fontSize: 11, color: "var(--text-dim)", minWidth: 32 }}>{fontSize}px</span>
    </div>
  );
}

const ghostBtn: CSSProperties = {
  padding: "4px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "transparent",
  color: "var(--text-secondary)",
  fontSize: 12,
  cursor: "pointer",
};

const iconBtn: CSSProperties = {
  width: 36,
  height: 26,
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  background: "transparent",
  color: "var(--text-secondary)",
  fontSize: 11,
  cursor: "pointer",
};

