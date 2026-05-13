import type { CSSProperties } from "react";

type Props = {
  fontSize: number;
  onFontDelta: (d: number) => void;
  onFormat: () => void;
};

export function EditorToolbar({ fontSize, onFontDelta, onFormat }: Props) {
  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        padding: "6px 8px",
        background: "var(--card)",
        borderBottom: "1px solid #e8e8e8",
        alignItems: "center",
      }}
    >
      <button type="button" title="格式化 (Black)" style={iconBtn} onClick={onFormat}>
        ⏎
      </button>
      <button type="button" title="缩小字体" style={iconBtn} onClick={() => onFontDelta(-1)}>
        A−
      </button>
      <button type="button" title="放大字体" style={iconBtn} onClick={() => onFontDelta(1)}>
        A+
      </button>
      <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: "auto" }}>{fontSize}px</span>
    </div>
  );
}

const iconBtn: CSSProperties = {
  width: 32,
  height: 28,
  border: "1px solid #d9d9d9",
  borderRadius: 4,
  background: "#fff",
  fontSize: 14,
};
