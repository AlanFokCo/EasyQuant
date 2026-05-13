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
    monaco.editor.defineTheme("eq-studio", {
      base: "vs",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#f0f2f5",
      },
    });
  }, []);

  const onMount = useCallback((ed: editor.IStandaloneCodeEditor, monaco: typeof import("monaco-editor")) => {
    editorRef.current = ed;
    monacoRef.current = monaco;
    monaco.editor.setTheme("eq-studio");
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
      theme="eq-studio"
      value={value}
      onChange={handleChange}
      beforeMount={beforeMount}
      onMount={onMount}
      options={{
        minimap: { enabled: true },
        fontSize,
        scrollBeyondLastLine: false,
        automaticLayout: true,
      }}
    />
  );
}
