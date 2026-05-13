import { useCallback, useEffect, useRef, useState } from "react";

import { apiOrigin } from "../api/client";
import { useEditorStore } from "../store/editorStore";

export type LogLine = { stream: string; line: string; ts?: string };

const FLUSH_MS = 50;

export function useRunStream(runId: string | null) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<{
    html_report_url?: string | null;
    json_report_url?: string | null;
  } | null>(null);
  const [doneStatus, setDoneStatus] = useState<string | null>(null);
  const buffer = useRef<LogLine[]>([]);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const setSseConnected = useEditorStore((s) => s.setSseConnected);

  const flush = useCallback(() => {
    if (!buffer.current.length) return;
    const batch = buffer.current.splice(0, buffer.current.length);
    setLogs((prev) => {
      const next = [...prev, ...batch];
        return next.length > 2000 ? next.slice(-2000) : next;
    });
  }, []);

  useEffect(() => {
    if (!runId) return;
    setLogs([]);
    setProgress(0);
    setStage(null);
    setArtifacts(null);
    setDoneStatus(null);
    buffer.current = [];

    const url = `${apiOrigin}/api/v1/runs/${runId}/stream`;
    const es = new EventSource(url);

    const scheduleFlush = () => {
      if (flushTimer.current) return;
      flushTimer.current = setTimeout(() => {
        flushTimer.current = null;
        flush();
      }, FLUSH_MS);
    };

    es.addEventListener("log", (e) => {
      try {
        const d = JSON.parse((e as MessageEvent).data);
        buffer.current.push({ stream: d.stream, line: d.line, ts: d.ts });
        scheduleFlush();
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("progress", (e) => {
      try {
        const d = JSON.parse((e as MessageEvent).data);
        if (typeof d.progress === "number") setProgress(d.progress);
        if (d.stage) setStage(d.stage);
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("done", (e) => {
      try {
        const d = JSON.parse((e as MessageEvent).data);
        setDoneStatus(d.status || "done");
        setArtifacts(d.artifacts || null);
        flush();
      } catch {
        /* ignore */
      }
      es.close();
    });

    es.addEventListener("error", () => {
      flush();
      es.close();
    });

    es.onopen = () => setSseConnected(true);
    es.onerror = () => setSseConnected(false);

    return () => {
      es.close();
      setSseConnected(false);
      if (flushTimer.current) clearTimeout(flushTimer.current);
      flush();
    };
  }, [runId, flush, setSseConnected]);

  return { logs, progress, stage, artifacts, doneStatus, clearLogs: () => setLogs([]) };
}
