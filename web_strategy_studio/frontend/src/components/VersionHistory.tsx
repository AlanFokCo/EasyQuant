import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DiffEditor } from "@monaco-editor/react";
import { useCallback, useState } from "react";

import { apiJson } from "../api/client";
import { useEditorStore } from "../store/editorStore";
import { monacoThemeName } from "../hooks/useTheme";
import { useTheme } from "../hooks/useTheme";

type VersionItem = {
  version: number;
  label: string | null;
  content_hash: string | null;
  created_at: string;
};

type DiffResult = {
  from_version: number;
  to_version: number;
  from_code: string;
  to_code: string;
  diff: string[];
};

type Props = {
  strategyId: string | null;
  currentVersion: number | null;
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function VersionHistory({ strategyId, currentVersion }: Props) {
  const qc = useQueryClient();
  const setShowVersions = useEditorStore((s) => s.setShowVersions);
  const addToast = useEditorStore((s) => s.addToast);
  const { resolvedTheme } = useTheme();
  const monacoTheme = monacoThemeName(resolvedTheme);

  const [diffPair, setDiffPair] = useState<[number, number] | null>(null);
  const [diffData, setDiffData] = useState<DiffResult | null>(null);

  // Fetch versions list
  const { data: versions, isLoading } = useQuery({
    queryKey: ["versions", strategyId],
    enabled: !!strategyId,
    queryFn: () => apiJson<VersionItem[]>(`/api/v1/strategies/${strategyId}/versions`),
    refetchInterval: false,
  });

  // Fetch diff when a pair is selected
  const diffMut = useMutation({
    mutationFn: async ([from, to]: [number, number]) => {
      if (!strategyId) throw new Error("no strategy");
      return apiJson<DiffResult>(
        `/api/v1/strategies/${strategyId}/versions/${from}/diff/${to}`
      );
    },
    onSuccess: (data) => setDiffData(data),
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "获取 diff 失败");
    },
  });

  // Restore version
  const restoreMut = useMutation({
    mutationFn: async (version: number) => {
      if (!strategyId) throw new Error("no strategy");
      return apiJson<{ id: string; version: number }>(
        `/api/v1/strategies/${strategyId}/versions/${version}/restore`,
        { method: "POST" }
      );
    },
    onSuccess: (result) => {
      addToast("success", `已恢复到版本 v${result.version}`);
      qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
      qc.invalidateQueries({ queryKey: ["versions", strategyId] });
    },
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "恢复失败");
    },
  });

  const handleShowDiff = useCallback(
    (from: number, to: number) => {
      setDiffPair([from, to]);
      setDiffData(null);
      diffMut.mutate([from, to]);
    },
    [diffMut]
  );

  const handleRestore = useCallback(
    (version: number) => {
      if (!strategyId) return;
      if (!window.confirm(`确定要恢复到版本 v${version}？这将创建一个新版本。`)) return;
      restoreMut.mutate(version);
    },
    [strategyId, restoreMut]
  );

  const handleCloseDiff = useCallback(() => {
    setDiffPair(null);
    setDiffData(null);
  }, []);

  // If showing diff view
  if (diffPair && diffData) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        {/* Diff header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "10px 14px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            版本对比: v{diffData.from_version} → v{diffData.to_version}
          </h3>
          <button
            type="button"
            onClick={handleCloseDiff}
            style={{
              padding: "4px 10px",
              borderRadius: 4,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-secondary)",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            返回列表
          </button>
        </div>
        {/* Monaco DiffEditor */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <DiffEditor
            height="100%"
            language="python"
            theme={monacoTheme}
            original={diffData.from_code}
            modified={diffData.to_code}
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 13,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              originalEditable: false,
            }}
          />
        </div>
      </div>
    );
  }

  // Diff loading state
  if (diffPair && !diffData) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
        加载 diff 中…
      </div>
    );
  }

  // Versions list view
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
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
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>版本历史</h3>
        <button
          type="button"
          onClick={() => setShowVersions(false)}
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

      {/* List */}
      <div style={{ flex: 1, overflow: "auto", padding: "4px 0" }}>
        {isLoading && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
            加载中…
          </div>
        )}
        {!isLoading && (!versions || versions.length === 0) && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
            暂无版本记录
          </div>
        )}
        {versions?.map((v, idx) => {
          const isCurrent = v.version === currentVersion;
          const prevVersion = idx < versions.length - 1 ? versions[idx + 1].version : null;
          return (
            <div
              key={v.version}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
                padding: "8px 14px",
                borderBottom: "1px solid var(--border-light)",
                background: isCurrent ? "var(--primary-bg)" : "transparent",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: "var(--mono)",
                    color: isCurrent ? "var(--primary)" : "var(--text)",
                  }}
                >
                  v{v.version}
                  {isCurrent && (
                    <span
                      style={{
                        marginLeft: 6,
                        fontSize: 10,
                        padding: "1px 6px",
                        borderRadius: 8,
                        background: "var(--primary)",
                        color: "#fff",
                        fontWeight: 500,
                      }}
                    >
                      当前
                    </span>
                  )}
                </span>
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                  {formatDate(v.created_at)}
                </span>
              </div>
              {v.label && (
                <div style={{ fontSize: 11, color: "var(--text-secondary)", fontStyle: "italic" }}>
                  {v.label}
                </div>
              )}
              <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
                {/* Restore button */}
                {!isCurrent && (
                  <button
                    type="button"
                    onClick={() => handleRestore(v.version)}
                    style={{
                      padding: "3px 10px",
                      borderRadius: 4,
                      border: "1px solid var(--primary)",
                      background: "var(--primary-bg)",
                      color: "var(--primary)",
                      fontSize: 11,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    恢复到此版本
                  </button>
                )}
                {/* Diff with previous version */}
                {prevVersion !== null && (
                  <button
                    type="button"
                    onClick={() => handleShowDiff(prevVersion, v.version)}
                    style={{
                      padding: "3px 10px",
                      borderRadius: 4,
                      border: "1px solid var(--border)",
                      background: "transparent",
                      color: "var(--text-secondary)",
                      fontSize: 11,
                      cursor: "pointer",
                    }}
                  >
                    对比 v{prevVersion}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
