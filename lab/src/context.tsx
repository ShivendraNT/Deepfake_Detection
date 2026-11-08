import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { api, type Health, type TechniqueInfo } from "./api";
import { useAsync } from "./lib/hooks";
import { indexTechniques, type TechIndex } from "./lib/stages";

// ------------------------------------------------------------------ workstation (health + techniques)

interface LabState {
  health: Health | null;
  healthError: Error | null;
  techniques: TechniqueInfo[];
  techIndex: TechIndex;
  /** Set by the case / evidence screens so the top bar can show the custody status. */
  activeCaseId: string | null;
  setActiveCaseId: (id: string | null) => void;
  custodyNonce: number;
  bumpCustody: () => void;
}

const LabContext = createContext<LabState | null>(null);

export function LabProvider({ children }: { children: ReactNode }) {
  const health = useAsync(api.health, "health", { pollMs: 30000 });
  const techs = useAsync(api.techniques, "techniques");
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [custodyNonce, setNonce] = useState(0);
  const bumpCustody = useCallback(() => setNonce((n) => n + 1), []);
  const value = useMemo<LabState>(
    () => ({
      health: health.data,
      healthError: health.error,
      techniques: techs.data ?? [],
      techIndex: indexTechniques(techs.data),
      activeCaseId,
      setActiveCaseId,
      custodyNonce,
      bumpCustody,
    }),
    [health.data, health.error, techs.data, activeCaseId, custodyNonce, bumpCustody],
  );
  return <LabContext.Provider value={value}>{children}</LabContext.Provider>;
}

export function useLab(): LabState {
  const v = useContext(LabContext);
  if (!v) throw new Error("useLab outside LabProvider");
  return v;
}

// ------------------------------------------------------------------ toasts

export type ToastTone = "info" | "success" | "error" | "warn";
export interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  body?: string;
}

interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">, ms?: number) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastState | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)), []);
  const push = useCallback(
    (t: Omit<Toast, "id">, ms = 5200) => {
      const id = next.current++;
      setToasts((ts) => [...ts.slice(-3), { ...t, id }]);
      window.setTimeout(() => dismiss(id), ms);
    },
    [dismiss],
  );
  const value = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss]);
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast(): ToastState {
  const v = useContext(ToastContext);
  if (!v) throw new Error("useToast outside ToastProvider");
  return v;
}
