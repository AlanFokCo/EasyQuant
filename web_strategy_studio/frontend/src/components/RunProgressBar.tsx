type Props = {
  progress: number;
  stage: string | null;
  running: boolean;
};

export function RunProgressBar({ progress, stage, running }: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
        {stage ? `阶段: ${stage}` : running ? "运行中…" : "空闲"}
      </div>
      <div
        role="progressbar"
        aria-label="回测进度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        style={{
          height: 6, /* spec: ≥6px */
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
