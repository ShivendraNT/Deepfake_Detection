import { useEffect, useRef, useState } from "react";
import { urls, type ProgressEvent } from "../api";

export type StreamState = "idle" | "connecting" | "open" | "done" | "error";

function eventKey(e: ProgressEvent): string {
  return `${e.stage}|${e.status}|${e.at ?? ""}|${e.progress}|${e.message}`;
}

function parseEvent(raw: string): ProgressEvent | null {
  try {
    const v = JSON.parse(raw) as Partial<ProgressEvent>;
    if (!v || typeof v.stage !== "string") return null;
    return {
      evidence_id: String(v.evidence_id ?? ""),
      stage: v.stage,
      message: typeof v.message === "string" ? v.message : "",
      progress: typeof v.progress === "number" ? v.progress : 0,
      at: typeof v.at === "string" ? v.at : undefined,
      status: typeof v.status === "string" ? v.status : "running",
    };
  } catch {
    return null;
  }
}

/**
 * Subscribe to GET /lab/api/evidence/{id}/events (Server-Sent Events).
 *
 * The server replays every event of the item from the start and closes the stream after the
 * first "done" event, so we close the EventSource ourselves on "done" (otherwise the browser
 * would reconnect and replay). Replayed duplicates are merged by key. On a network error we
 * retry a few times, then report "error" so the caller can fall back to polling.
 */
export function useEvidenceStream(
  evidenceId: string | null | undefined,
  enabled: boolean,
  onDone?: (e: ProgressEvent) => void,
): { events: ProgressEvent[]; state: StreamState } {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [state, setState] = useState<StreamState>("idle");
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    setEvents([]);
    if (!evidenceId || !enabled || typeof EventSource === "undefined") {
      setState("idle");
      return;
    }
    const seen = new Set<string>();
    let es: EventSource | null = null;
    let stopped = false;
    let retries = 0;
    let retryTimer: number | null = null;

    const connect = () => {
      if (stopped) return;
      setState("connecting");
      es = new EventSource(urls.events(evidenceId));
      es.onopen = () => {
        if (!stopped) setState("open");
      };
      es.onmessage = (m: MessageEvent<string>) => {
        const ev = parseEvent(m.data);
        if (!ev || stopped) return;
        const k = eventKey(ev);
        if (!seen.has(k)) {
          seen.add(k);
          setEvents((prev) => [...prev, ev]);
        }
        if (ev.stage === "done") {
          stopped = true;
          es?.close();
          setState("done");
          onDoneRef.current?.(ev);
        }
      };
      es.onerror = () => {
        if (stopped) return;
        es?.close();
        if (retries < 3) {
          retries += 1;
          setState("connecting");
          retryTimer = window.setTimeout(connect, 1500 * retries);
        } else {
          stopped = true;
          setState("error");
        }
      };
    };
    connect();
    return () => {
      stopped = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      es?.close();
    };
  }, [evidenceId, enabled]);

  return { events, state };
}
