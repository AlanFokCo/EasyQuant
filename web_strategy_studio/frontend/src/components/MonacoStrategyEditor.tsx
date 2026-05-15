import type { editor } from "monaco-editor";
import Editor from "@monaco-editor/react";
import { useCallback, useEffect, useRef } from "react";

import { apiOrigin } from "../api/client";

type Props = {
  value: string;
  onChange: (v: string) => void;
  markers?: editor.IMarkerData[];
  fontSize: number;
  monacoTheme?: string;
};

// Trigger characters: dot, underscore, and all ASCII letters
const _TRIGGER_CHARS = Array.from(
  "._abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
);

// Last-call-wins debounce for the async completion fetch.
// Promises from earlier calls within the debounce window are intentionally
// never resolved — Monaco only needs the result for the most recent keystroke,
// and the provider is called again on the next trigger anyway.
function _makeDebounced(fn: (sourceCode: string, cursorLine: number, cursorCol: number) => Promise<unknown>, ms: number) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (sourceCode: string, cursorLine: number, cursorCol: number) =>
    new Promise<unknown>((resolve, reject) => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        fn(sourceCode, cursorLine, cursorCol).then(resolve, reject);
      }, ms);
    });
}

export function MonacoStrategyEditor({ value, onChange, markers, fontSize, monacoTheme }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const completionDisposable = useRef<{ dispose(): void } | null>(null);

  const beforeMount = useCallback((monaco: typeof import("monaco-editor")) => {
    monaco.editor.defineTheme("eq-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#0d1117",
        "editor.foreground": "#e6edf3",
        "editor.lineHighlightBackground": "#161b22",
        "editorLineNumber.foreground": "#484f58",
        "editorLineNumber.activeForeground": "#8b949e",
        "editor.selectionBackground": "#264f78",
        "editor.inactiveSelectionBackground": "#3a3d41",
        "editorCursor.foreground": "#e6edf3",
        "editor.findMatchBackground": "#515c6a",
        "editor.findMatchHighlightBackground": "#ea5c0055",
        "editorBracketMatch.background": "#0d1117",
        "editorBracketMatch.border": "#8b949e",
      },
    });
  }, []);

  const onMount = useCallback((ed: editor.IStandaloneCodeEditor, monaco: typeof import("monaco-editor")) => {
    editorRef.current = ed;
    monacoRef.current = monaco;
    // Set theme at mount time only; subsequent theme changes are handled by
    // the monacoTheme useEffect below.
    monaco.editor.setTheme(monacoTheme ?? "eq-dark");

    // B20: Register eqlib completion provider backed by /api/v1/completion.
    // Dispose any previous registration first (handles HMR / double-mount).
    completionDisposable.current?.dispose();

    const kindMap: Record<string, number> = {
      Function: monaco.languages.CompletionItemKind.Function,
      Method: monaco.languages.CompletionItemKind.Method,
      Class: monaco.languages.CompletionItemKind.Class,
      Variable: monaco.languages.CompletionItemKind.Variable,
      Keyword: monaco.languages.CompletionItemKind.Keyword,
    };

    type RawSuggestion = {
      label: string;
      kind: string;
      insert_text: string;
      documentation?: string;
    };

    const fetchSuggestions = _makeDebounced(
      async (sourceCode: string, cursorLine: number, cursorCol: number) => {
        const res = await fetch(`${apiOrigin}/api/v1/completion`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_code: sourceCode,
            cursor_line: cursorLine,
            cursor_col: cursorCol,
          }),
        });
        if (!res.ok) return [];
        const data = await res.json() as { suggestions: RawSuggestion[] };
        return data.suggestions ?? [];
      },
      200,
    );

    completionDisposable.current = monaco.languages.registerCompletionItemProvider("python", {
      triggerCharacters: _TRIGGER_CHARS,
      provideCompletionItems: async (model, position) => {
        const sourceCode = model.getValue();
        const suggestions = await fetchSuggestions(
          sourceCode,
          position.lineNumber,
          position.column,
        ) as RawSuggestion[];

        const range = {
          startLineNumber: position.lineNumber,
          startColumn: position.column,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        };

        return {
          suggestions: suggestions.map((s) => ({
            label: s.label,
            kind: kindMap[s.kind] ?? monaco.languages.CompletionItemKind.Text,
            insertText: s.insert_text,
            documentation: s.documentation,
            range,
          })),
        };
      },
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- monacoTheme used for initial mount only; theme sync handled by dedicated useEffect
  }, []);

  // Dispose the completion provider when the component unmounts.
  useEffect(() => {
    return () => {
      completionDisposable.current?.dispose();
    };
  }, []);

  // Sync Monaco editor theme whenever resolvedTheme changes
  useEffect(() => {
    const monaco = monacoRef.current;
    if (!monaco || !monacoTheme) return;
    monaco.editor.setTheme(monacoTheme);
  }, [monacoTheme]);

  useEffect(() => {
    const ed = editorRef.current;
    const monaco = monacoRef.current;
    const model = ed?.getModel();
    if (!ed || !monaco || !model) return;
    monaco.editor.setModelMarkers(model, "easyquant", markers ?? []);
  }, [markers]);

  const handleChange = useCallback(
    (v: string | undefined) => {
      onChange(v ?? "");
    },
    [onChange]
  );

  return (
    <Editor
      height="100%"
      defaultLanguage="python"
      theme={monacoTheme ?? "eq-dark"}
      value={value}
      onChange={handleChange}
      beforeMount={beforeMount}
      onMount={onMount}
      options={{
        minimap: { enabled: true },
        fontSize,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        renderLineHighlight: "line",
        smoothScrolling: true,
        cursorBlinking: "smooth",
        padding: { top: 8, bottom: 8 },
      }}
    />
  );
}
