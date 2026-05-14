import type { CSSProperties } from "react";
import { Virtuoso } from "react-virtuoso";

import type { LogLine } from "../hooks/useRunStream";

type Props = {
  lines: LogLine[];
  onClear: () => void;
  onDownload: () => void;
};

export function LogConsole({ lines, onClear, onDownload }: Props) {
  return (
    <div
      style={{
        flex: 1,
        minHeight: 120,
        background: "var(--bg-secondary)",
        borderRadius: "var(--radius)",
        border: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 10px",
          borderBottom: "1px solid var(--border)",
          fontSize: 12,
          color: "var(--text-secondary)",
        }}
      >
        <span>运行日志</span>
        <span>
          <button type="button" style={btnStyle} onClick={onClear}>
            清空
          </button>
          <button type="button" style={btnStyle} onClick={onDownload}>
            下载
          </button>
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <Virtuoso
          style={{ height: "100%" }}
          data={lines}
          followOutput="smooth"
          itemContent={(_, row) => (
            <pre
              style={{
                margin: 0,
                padding: "2px 8px",
                fontSize: 12,
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                color: row.stream === "stderr" ? "var(--error)" : "var(--text-dim)",
                fontFamily: "var(--mono)",
                lineHeight: 1.6,
              }}
            >
              [{row.stream}] {row.line}
            </pre>
          )}
        />
      </div>
    </div>
  );
}

const btnStyle: CSSProperties = {
  marginLeft: 6,
  padding: "2px 8px",
  fontSize: 12,
  border: "1px solid var(--border)",
  borderRadius: 4,
  background: "transparent",
  color: "var(--text-secondary)",
};
