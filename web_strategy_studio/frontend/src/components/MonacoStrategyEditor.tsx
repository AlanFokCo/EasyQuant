import type { editor } from "monaco-editor";
import Editor from "@monaco-editor/react";
import { useCallback, useEffect, useRef } from "react";

type Props = {
  value: string;
  onChange: (v: string) => void;
  markers?: editor.IMarkerData[];
  fontSize: number;
};

export function MonacoStrategyEditor({ value, onChange, markers, fontSize }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);

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
    monaco.editor.setTheme("eq-dark");
  }, []);

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
      theme="eq-dark"
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
