import { useCallback, useEffect, useRef, useState } from "react";

import { apiOrigin } from "../api/client";
import { useEditorStore } from "../store/editorStore";

export type LogLine = { stream: string; line: string; ts?: string };

const FLUSH_MS = 50;
const LS_RUN_KEY = "eq_studio_run_id";

// Exponential backoff: 1s → 2s → 4s → … → 30s max.
function nextBackoff(prev: number): number {
  return Math.min(prev * 2, 30_000);
}

export function useRunStream(runId: string | null) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<{
    html_report_url?: string | null;
    json_report_url?: string | null;
  } | null>(null);
  const [doneStatus, setDoneStatus] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const buffer = useRef<LogLine[]>([]);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const setSseConnected = useEditorStore((s) => s.setSseConnected);
  const setSseReconnecting = useEditorStore((s) => s.setSseReconnecting);

  // Track the last event ID received for Last-Event-ID replay.
  const lastEventId = useRef<number>(-1);
  // Whether this stream has completed (terminal event received).
  const done = useRef(false);

  const flush = useCallback(() => {
    if (!buffer.current.length) return;
    const batch = buffer.current.splice(0, buffer.current.length);
    setLogs((prev) => {
      const next = [...prev, ...batch];
      return next.length > 2000 ? next.slice(-2000) : next;
    });
  }, []);

  useEffect(() => {
    if (!runId) {
      // Clear localStorage when run is cleared
      localStorage.removeItem(LS_RUN_KEY);
      return;
    }

    // Persist to localStorage for reattach-after-refresh (B7)
    localStorage.setItem(LS_RUN_KEY, runId);

    setLogs([]);
    setProgress(0);
    setStage(null);
    setArtifacts(null);
    setDoneStatus(null);
    buffer.current = [];
    lastEventId.current = -1;
    done.current = false;

    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let backoff = 1_000;
    let cancelled = false;

    const connect = () => {
      if (cancelled || done.current) return;

      const params = lastEventId.current >= 0
        ? `?last_event_id=${lastEventId.current}`
        : "";
      const url = `${apiOrigin}/api/v1/runs/${runId}/stream${params}`;

      es = new EventSource(url);

      const scheduleFlush = () => {
        if (flushTimer.current) return;
        flushTimer.current = setTimeout(() => {
          flushTimer.current = null;
          flush();
        }, FLUSH_MS);
      };

      es.addEventListener("log", (e) => {
        try {
          const raw = e as MessageEvent;
          if (raw.lastEventId) lastEventId.current = parseInt(raw.lastEventId, 10);
          const d = JSON.parse(raw.data);
          buffer.current.push({ stream: d.stream, line: d.line, ts: d.ts });
          scheduleFlush();
        } catch { /* ignore */ }
      });

      es.addEventListener("progress", (e) => {
        try {
          const raw = e as MessageEvent;
          if (raw.lastEventId) lastEventId.current = parseInt(raw.lastEventId, 10);
          const d = JSON.parse(raw.data);
          if (typeof d.progress === "number") setProgress(d.progress);
          if (d.stage) setStage(d.stage);
        } catch { /* ignore */ }
      });

      es.addEventListener("done", (e) => {
        try {
          const raw = e as MessageEvent;
          if (raw.lastEventId) lastEventId.current = parseInt(raw.lastEventId, 10);
          const d = JSON.parse(raw.data);
          setDoneStatus(d.status || "done");
          setArtifacts(d.artifacts || null);
          flush();
        } catch { /* ignore */ }
        done.current = true;
        es?.close();
        setSseConnected(false);
        setSseReconnecting(false);
        setReconnecting(false);
        // Remove from localStorage once done
        localStorage.removeItem(LS_RUN_KEY);
      });

      es.addEventListener("error", (_e) => {
        flush();
        es?.close();
        setSseConnected(false);
        if (!done.current && !cancelled) {
          // Exponential backoff reconnect
          setSseReconnecting(true);
          setReconnecting(true);
          retryTimer = setTimeout(() => {
            backoff = nextBackoff(backoff);
            connect();
          }, backoff);
        }
      });

      es.onopen = () => {
        setSseConnected(true);
        setSseReconnecting(false);
        setReconnecting(false);
        backoff = 1_000; // reset on successful connection
      };
    };

    connect();

    return () => {
      cancelled = true;
      es?.close();
      setSseConnected(false);
      setSseReconnecting(false);
      if (retryTimer) clearTimeout(retryTimer);
      if (flushTimer.current) clearTimeout(flushTimer.current);
      flush();
    };
  }, [runId, flush, setSseConnected, setSseReconnecting]);

  return {
    logs,
    progress,
    stage,
    artifacts,
    doneStatus,
    reconnecting,
    clearLogs: () => setLogs([]),
  };
}

/** Read the persisted runId from localStorage (for reattach-after-refresh). */
export function getPersistedRunId(): string | null {
  return localStorage.getItem(LS_RUN_KEY);
}
