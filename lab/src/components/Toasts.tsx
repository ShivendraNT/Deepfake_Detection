import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useToast, type ToastTone } from "../context";

const TONE: Record<ToastTone, { icon: typeof Info; cls: string }> = {
  info: { icon: Info, cls: "text-accent" },
  success: { icon: CheckCircle2, cls: "text-emerald-400" },
  warn: { icon: AlertTriangle, cls: "text-amber-400" },
  error: { icon: XCircle, cls: "text-red-400" },
};

export function Toasts() {
  const { toasts, dismiss } = useToast();
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[70] flex w-[380px] max-w-[calc(100vw-2.5rem)] flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const { icon: Icon, cls } = TONE[t.tone];
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 24, scale: 0.98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, scale: 0.98 }}
              className="panel pointer-events-auto flex items-start gap-3 p-3.5"
            >
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-100">{t.title}</div>
                {t.body && <div className="mt-0.5 break-words text-xs text-slate-400">{t.body}</div>}
              </div>
              <button type="button" className="text-slate-500 hover:text-slate-200" onClick={() => dismiss(t.id)} aria-label="Dismiss">
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
