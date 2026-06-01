import { useCallback, useEffect, useRef, useState } from "react";

import { apiOrigin, getToken } from "../api/client";
import { useEditorStore } from "../store/editorStore";

export type LogLine = { stream: string; line: string; ts?: string };

const FLUSH_MS = 50;
// HIGH-20: per-tab runId via sessionStorage (not global localStorage)
const SS_RUN_KEY = "eq_studio_run_id";

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
  const [doneError, setDoneError] = useState<{ code: string; message: string } | null>(null);
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

  // Track mounted state to avoid setState on unmounted component
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Safe flush that checks mounted state
  const safeFlush = useCallback(() => {
    if (!mountedRef.current) return;
    flush();
  }, [flush]);

  useEffect(() => {
    if (!runId) {
      // HIGH-20: use sessionStorage (per-tab)
      sessionStorage.removeItem(SS_RUN_KEY);
      return;
    }

    // Persist to sessionStorage for reattach (HIGH-20)
    sessionStorage.setItem(SS_RUN_KEY, runId);

    setLogs([]);
    setProgress(0);
    setStage(null);
    setArtifacts(null);
    setDoneStatus(null);
    setDoneError(null);
    buffer.current = [];
    lastEventId.current = -1;
    done.current = false;

    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let backoff = 1_000;
    let cancelled = false;

    const fetchSseToken = async (): Promise<string | null> => {
      const mainToken = getToken();
      if (!mainToken) return null;
      try {
        const resp = await fetch(`${apiOrigin}/api/v1/auth/sse-token`, {
          method: "POST",
          headers: { Authorization: `Bearer ${mainToken}` },
        });
        if (!resp.ok) return null;
        const data = await resp.json();
        return data.token ?? null;
      } catch {
        return null;
      }
    };

    const connect = async () => {
      if (cancelled || done.current) return;

      const sseToken = await fetchSseToken();
      const token = sseToken ?? getToken();
      const parts: string[] = [];
      if (token) parts.push(`token=${encodeURIComponent(token)}`);
      if (lastEventId.current >= 0) parts.push(`last_event_id=${lastEventId.current}`);
      const qs = parts.length > 0 ? `?${parts.join("&")}` : "";
      const url = `${apiOrigin}/api/v1/runs/${runId}/stream${qs}`;

      es = new EventSource(url);

      const scheduleFlush = () => {
        if (flushTimer.current) return;
        flushTimer.current = setTimeout(() => {
          flushTimer.current = null;
          safeFlush();
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
          if (d.status === "failed") {
            setDoneError({ code: d.error_code || "UNKNOWN", message: d.error_message || "Unknown error" });
          } else {
            setDoneError(null);
          }
          safeFlush();
        } catch { /* ignore */ }
        done.current = true;
        es?.close();
        setSseConnected(false);
        setSseReconnecting(false);
        setReconnecting(false);
        // Remove from sessionStorage once done
        sessionStorage.removeItem(SS_RUN_KEY);
      });

      es.addEventListener("error", (_e) => {
        safeFlush();
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
      // Don't flush on cleanup - component is unmounting
      // and we shouldn't update state after unmount
    };
  }, [runId, safeFlush, setSseConnected, setSseReconnecting]);

  return {
    logs,
    progress,
    stage,
    artifacts,
    doneStatus,
    doneError,
    reconnecting,
    clearLogs: () => setLogs([]),
  };
}

/** HIGH-20: Read the per-tab persisted runId from sessionStorage. */
export function getPersistedRunId(): string | null {
  return sessionStorage.getItem(SS_RUN_KEY);
}
