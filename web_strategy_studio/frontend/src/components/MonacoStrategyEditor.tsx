import type { editor } from "monaco-editor";
import Editor from "@monaco-editor/react";
import { useCallback, useEffect, useRef } from "react";

import { apiOrigin, getToken } from "../api/client";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSave?: () => void;
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

export function MonacoStrategyEditor({ value, onChange, onSave, markers, fontSize, monacoTheme }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const completionDisposable = useRef<{ dispose(): void } | null>(null);
  const onSaveRef = useRef(onSave);
  onSaveRef.current = onSave;

  const beforeMount = useCallback((monaco: typeof import("monaco-editor")) => {
    monaco.editor.defineTheme("eq-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "6a737d", fontStyle: "italic" },
        { token: "keyword", foreground: "f97583" },
        { token: "string", foreground: "9ecbff" },
        { token: "number", foreground: "79b8ff" },
        { token: "identifier", foreground: "e6edf3" },
      ],
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
        "editorIndentGuide.background": "#2d333b",
        "editorIndentGuide.activeBackground": "#484f58",
      },
    });

    monaco.editor.defineTheme("eq-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "6a737d", fontStyle: "italic" },
        { token: "keyword", foreground: "d73a49" },
        { token: "string", foreground: "032f62" },
        { token: "number", foreground: "005cc5" },
      ],
      colors: {
        "editor.background": "#ffffff",
        "editor.foreground": "#24292e",
        "editor.lineHighlightBackground": "#f6f8fa",
      },
    });
  }, []);

  const onMount = useCallback((ed: editor.IStandaloneCodeEditor, monaco: typeof import("monaco-editor")) => {
    editorRef.current = ed;
    monacoRef.current = monaco;
    // Set theme at mount time only; subsequent theme changes are handled by
    // the monacoTheme useEffect below.
    monaco.editor.setTheme(monacoTheme ?? "eq-dark");

    // Cmd+S / Ctrl+S → manual save (creates version snapshot)
    ed.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
      () => {
        onSaveRef.current?.();
      }
    );

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
        const token = getToken();
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch(`${apiOrigin}/api/v1/completion`, {
          method: "POST",
          headers,
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
        fontFamily: "'JetBrains Mono', 'Fira Code', Menlo, Monaco, monospace",
        fontLigatures: true,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        renderLineHighlight: "all",
        smoothScrolling: true,
        cursorBlinking: "smooth",
        cursorSmoothCaretAnimation: "on",
        padding: { top: 8, bottom: 8 },
        // Code folding
        folding: true,
        foldingStrategy: "indentation",
        showFoldingControls: "mouseover",
        // Bracket matching
        bracketPairColorization: { enabled: true },
        guides: {
          bracketPairs: true,
          indentation: true,
        },
        // Line numbers
        lineNumbers: "on",
        renderLineHighlightOnlyWhenFocus: false,
        // Word wrap
        wordWrap: "on",
        // Indentation
        tabSize: 4,
        insertSpaces: true,
        // Selection
        roundedSelection: true,
        // Performance
        largeFileOptimizations: true,
      }}
    />
  );
}
