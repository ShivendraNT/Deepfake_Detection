import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  /** Re-run the request. Keeps the current data while loading (no flicker). */
  reload: () => Promise<T | null>;
  setData: (d: T | null) => void;
}

/**
 * Run an async request when `key` changes; optionally re-poll silently every `pollMs`
 * (null/0 = off). Responses that arrive after a newer request started are ignored.
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  key: string,
  opts: { pollMs?: number | null; enabled?: boolean } = {},
): AsyncState<T> {
  const { pollMs = null, enabled = true } = opts;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async (): Promise<T | null> => {
    const my = ++seq.current;
    try {
      const d = await fnRef.current();
      if (my === seq.current) {
        setData(d);
        setError(null);
      }
      return d;
    } catch (e) {
      if (my === seq.current) setError(e instanceof Error ? e : new Error(String(e)));
      return null;
    } finally {
      if (my === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    setData(null);
    setError(null);
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  useEffect(() => {
    if (!enabled || !pollMs) return;
    const t = window.setInterval(() => void run(), pollMs);
    return () => window.clearInterval(t);
  }, [enabled, pollMs, run, key]);

  return { data, error, loading, reload: run, setData };
}

/** Animate a number from its previous value to `target` (ease-out), for counters and gauges. */
export function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    const b = Number.isFinite(target) ? target : 0;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = a + (b - a) * eased;
      setValue(v);
      if (t < 1) raf = requestAnimationFrame(tick);
      else from.current = b;
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      from.current = b;
    };
  }, [target, durationMs]);
  return value;
}

/** Copy text to the clipboard; returns [copied, copy]. */
export function useCopy(resetMs = 1600): [boolean, (text: string) => Promise<void>] {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  const copy = useCallback(
    async (text: string) => {
      let ok = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          ok = true;
        }
      } catch {
        ok = false;
      }
      if (!ok) {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try {
          document.execCommand("copy");
        } finally {
          document.body.removeChild(ta);
        }
      }
      setCopied(true);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), resetMs);
    },
    [resetMs],
  );
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );
  return [copied, copy];
}

/** Close on Escape. */
export function useEscape(onEscape: () => void, active = true): void {
  useEffect(() => {
    if (!active) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onEscape();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onEscape, active]);
}

/** Track whether an image URL loads (artifacts may 404). */
export function useImageOk(src: string | null | undefined): "loading" | "ok" | "error" | "none" {
  const [state, setState] = useState<"loading" | "ok" | "error" | "none">(src ? "loading" : "none");
  useEffect(() => {
    if (!src) {
      setState("none");
      return;
    }
    setState("loading");
    const img = new Image();
    let alive = true;
    img.onload = () => alive && setState("ok");
    img.onerror = () => alive && setState("error");
    img.src = src;
    return () => {
      alive = false;
    };
  }, [src]);
  return state;
}
