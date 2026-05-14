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
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        style={{
          height: 4,
          borderRadius: 2,
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
          }}
        />
      </div>
    </div>
  );
}
