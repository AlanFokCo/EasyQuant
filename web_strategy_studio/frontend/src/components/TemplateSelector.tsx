import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { apiJson } from "../api/client";
import { useEditorStore } from "../store/editorStore";

type TemplateSummary = {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
};

type TemplateDetail = {
  id: string;
  name: string;
  description: string;
  code: string;
  category: string;
  tags: string[];
};

const CATEGORY_LABELS: Record<string, string> = {
  trend: "趋势",
  oscillation: "震荡",
  general: "通用",
};

type Props = {
  onSelect: (code: string, name: string) => void;
};

export function TemplateSelector({ onSelect }: Props) {
  const setShowTemplates = useEditorStore((s) => s.setShowTemplates);
  const addToast = useEditorStore((s) => s.addToast);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [previewCode, setPreviewCode] = useState<string | null>(null);

  // Fetch template list
  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates"],
    queryFn: () => apiJson<TemplateSummary[]>("/api/v1/templates"),
    staleTime: 5 * 60 * 1000,
  });

  // Fetch template detail for preview
  const detailMut = useMutation({
    mutationFn: (id: string) =>
      apiJson<TemplateDetail>(`/api/v1/templates/${id}`),
    onSuccess: (data) => {
      setPreviewCode(data.code);
    },
    onError: (e: unknown) => {
      addToast("error", e instanceof Error ? e.message : "获取模板失败");
    },
  });

  const handlePreview = useCallback(
    (id: string) => {
      setSelectedId(id);
      setPreviewCode(null);
      detailMut.mutate(id);
    },
    [detailMut]
  );

  const handleApply = useCallback(() => {
    if (!selectedId || !previewCode) return;
    const template = templates?.find((t) => t.id === selectedId);
    if (!template) return;
    if (
      !window.confirm(
        `确定要使用模板「${template.name}」？这将替换当前代码。`
      )
    )
      return;
    onSelect(previewCode, template.name);
    setShowTemplates(false);
    addToast("success", `已应用模板「${template.name}」`);
  }, [selectedId, previewCode, templates, onSelect, setShowTemplates, addToast]);

  const handleClose = useCallback(() => {
    setShowTemplates(false);
  }, [setShowTemplates]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
      }}
      onClick={handleClose}
    >
      <div
        style={{
          width: "90vw",
          maxWidth: 800,
          maxHeight: "80vh",
          background: "var(--bg-surface, var(--bg-secondary))",
          borderRadius: 12,
          border: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>策略模板</h2>
          <button
            type="button"
            onClick={handleClose}
            style={{
              padding: "4px 10px",
              borderRadius: 4,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-secondary)",
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            ×
          </button>
        </div>

        {/* Body: two-pane layout */}
        <div style={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>
          {/* Left: template list */}
          <div
            style={{
              width: 260,
              flexShrink: 0,
              borderRight: "1px solid var(--border)",
              overflow: "auto",
              padding: "8px 0",
            }}
          >
            {isLoading && (
              <div style={{ padding: 16, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
                加载中…
              </div>
            )}
            {templates?.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => handlePreview(t.id)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 16px",
                  border: "none",
                  borderBottom: "1px solid var(--border-light)",
                  background: selectedId === t.id ? "var(--primary-bg)" : "transparent",
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                  {t.name}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>
                  {CATEGORY_LABELS[t.category] ?? t.category}
                </div>
              </button>
            ))}
          </div>

          {/* Right: preview */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {selectedId && previewCode ? (
              <>
                {/* Template info */}
                <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>
                    {templates?.find((t) => t.id === selectedId)?.name}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
                    {templates?.find((t) => t.id === selectedId)?.description}
                  </div>
                  {/* Tags */}
                  <div style={{ display: "flex", gap: 4, marginTop: 8, flexWrap: "wrap" }}>
                    {templates
                      ?.find((t) => t.id === selectedId)
                      ?.tags.map((tag) => (
                        <span
                          key={tag}
                          style={{
                            fontSize: 10,
                            padding: "2px 8px",
                            borderRadius: 10,
                            background: "var(--primary-bg)",
                            color: "var(--primary)",
                          }}
                        >
                          {tag}
                        </span>
                      ))}
                  </div>
                </div>
                {/* Code preview */}
                <div style={{ flex: 1, overflow: "auto" }}>
                  <pre
                    style={{
                      margin: 0,
                      padding: 16,
                      fontSize: 12,
                      fontFamily: "var(--mono, 'JetBrains Mono', monospace)",
                      lineHeight: 1.6,
                      color: "var(--text)",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {previewCode}
                  </pre>
                </div>
              </>
            ) : selectedId && !previewCode ? (
              <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", fontSize: 13 }}>
                加载模板中…
              </div>
            ) : (
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--text-dim)",
                  fontSize: 13,
                }}
              >
                从左侧选择一个模板
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            padding: "12px 20px",
            borderTop: "1px solid var(--border)",
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            style={{
              padding: "8px 16px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-secondary)",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={!selectedId || !previewCode}
            style={{
              padding: "8px 20px",
              borderRadius: 6,
              border: "none",
              background: selectedId && previewCode ? "var(--primary)" : "var(--text-dim)",
              color: "#fff",
              fontSize: 13,
              fontWeight: 600,
              cursor: selectedId && previewCode ? "pointer" : "not-allowed",
              opacity: selectedId && previewCode ? 1 : 0.5,
            }}
          >
            应用模板
          </button>
        </div>
      </div>
    </div>
  );
}
