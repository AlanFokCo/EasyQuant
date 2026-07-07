import type { editor } from "monaco-editor";
import { MarkerSeverity } from "monaco-editor";
import { useMemo } from "react";

type LintLike = {
  syntax_errors: { line: number; col: number; message: string }[];
  lint_issues: { code: string; line: number; col: number; message: string }[];
  security_notes: { code: string; line: number; message: string }[];
};

export function useLintMarkers(lint: LintLike | null): editor.IMarkerData[] {
  return useMemo(() => {
    if (!lint) return [];
    const markers: editor.IMarkerData[] = [];

    for (const s of lint.syntax_errors) {
      markers.push({
        severity: MarkerSeverity.Error,
        message: s.message,
        startLineNumber: s.line,
        startColumn: Math.max(1, s.col),
        endLineNumber: s.line,
        endColumn: Math.max(s.col + 1, s.col + 2),
      });
    }

    for (const i of lint.lint_issues) {
      markers.push({
        severity: MarkerSeverity.Warning,
        message: `${i.code}: ${i.message}`,
        startLineNumber: i.line,
        startColumn: Math.max(1, i.col),
        endLineNumber: i.line,
        endColumn: i.col + 8,
      });
    }

    for (const n of lint.security_notes) {
      markers.push({
        severity: MarkerSeverity.Warning,
        message: `${n.code}: ${n.message}`,
        startLineNumber: n.line,
        startColumn: 1,
        endLineNumber: n.line,
        endColumn: 40,
      });
    }

    return markers;
  }, [lint]);
}
