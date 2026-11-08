import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { useCallback, useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useEscape } from "../lib/hooks";
import { cx, SafeImg } from "./ui";

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = "max-w-2xl",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEscape(onClose, open);
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-950/75 p-4 pt-[6vh] backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
          role="dialog"
          aria-modal="true"
        >
          <motion.div
            className={cx("panel w-full", width)}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 260, damping: 26 }}
          >
            <div className="flex items-start justify-between gap-4 border-b hairline px-6 py-4">
              <div>
                <div className="text-lg font-semibold text-white">{title}</div>
                {subtitle && <div className="mt-0.5 text-sm text-slate-400">{subtitle}</div>}
              </div>
              <button type="button" className="btn-ghost btn-sm -mr-2" onClick={onClose} aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="px-6 py-5">{children}</div>
            {footer && <div className="flex justify-end gap-2 border-t hairline px-6 py-4">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export interface LightboxItem {
  src: string;
  title: string;
  caption?: string;
  meta?: string;
}

export function Lightbox({
  items,
  index,
  onIndex,
  onClose,
}: {
  items: LightboxItem[];
  index: number | null;
  onIndex: (i: number) => void;
  onClose: () => void;
}) {
  const open = index !== null && index >= 0 && index < items.length;
  const item = open ? items[index] : undefined;
  useEscape(onClose, open);
  const step = useCallback(
    (d: number) => {
      if (index === null || items.length < 2) return;
      onIndex((index + d + items.length) % items.length);
    },
    [index, items.length, onIndex],
  );
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, step]);

  return createPortal(
    <AnimatePresence>
      {open && item && (
        <motion.div
          className="fixed inset-0 z-[60] flex flex-col bg-ink-950/92 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          role="dialog"
          aria-modal="true"
        >
          <div className="flex items-center justify-between gap-4 border-b hairline px-6 py-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-white">{item.title}</div>
              {item.meta && <div className="truncate font-mono text-2xs text-slate-500">{item.meta}</div>}
            </div>
            <div className="flex items-center gap-1">
              {items.length > 1 && (
                <span className="mr-2 font-mono text-xs text-slate-500">
                  {(index ?? 0) + 1} / {items.length}
                </span>
              )}
              <a className="btn-ghost btn-sm" href={item.src} download target="_blank" rel="noreferrer">
                <Download className="h-4 w-4" />
              </a>
              <button type="button" className="btn-ghost btn-sm" onClick={onClose} aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
          <div
            className="relative flex min-h-0 flex-1 items-center justify-center p-6"
            onMouseDown={(e) => {
              if (e.target === e.currentTarget) onClose();
            }}
          >
            {items.length > 1 && (
              <button
                type="button"
                className="absolute left-4 top-1/2 z-10 -translate-y-1/2 rounded-full border border-white/10 bg-ink-800/80 p-2 text-slate-300 hover:text-white"
                onClick={() => step(-1)}
                aria-label="Previous"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
            )}
            <motion.div
              key={item.src}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="checker flex max-h-full max-w-full items-center justify-center overflow-hidden rounded-xl border border-white/10"
            >
              <SafeImg
                src={item.src}
                alt={item.title}
                className="max-h-[calc(100vh-220px)] max-w-[calc(100vw-140px)] object-contain"
                fallback={<div className="p-16 text-sm text-slate-500">This artifact is not available on the workstation.</div>}
              />
            </motion.div>
            {items.length > 1 && (
              <button
                type="button"
                className="absolute right-4 top-1/2 z-10 -translate-y-1/2 rounded-full border border-white/10 bg-ink-800/80 p-2 text-slate-300 hover:text-white"
                onClick={() => step(1)}
                aria-label="Next"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            )}
          </div>
          {item.caption && (
            <div className="border-t hairline px-6 py-3 text-center text-sm text-slate-400">{item.caption}</div>
          )}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
