import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  Copy as CopyIcon,
  FileWarning,
  Fingerprint,
  Inbox,
  Loader2,
  Lock,
  ShieldCheck,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { useCallback, useMemo, useRef, useState, type DragEvent } from "react";
import { ApiError, uploadEvidence, type CaseView, type EvidenceRole, type UploadResult } from "../../api";
import { CopyButton, cx, EmptyState, ExhibitBadge, MediaIcon, ProgressBar } from "../../components/ui";
import { useToast } from "../../context";
import { formatBytes, plural } from "../../lib/format";
import { isFlagged, isPending } from "../../lib/verdict";
import { EvidenceCard } from "./EvidenceCard";

const ACCEPT = "image/*,audio/*,video/*,.opus,.amr,.m4a,.aac,.heic,.heif,.mov,.mkv,.webm,.3gp,.ogg,.wav,.flac";
const MAX_LIVE_STREAMS = 3;

function guessKind(f: File): string {
  if (f.type.startsWith("image/")) return "image";
  if (f.type.startsWith("audio/")) return "audio";
  if (f.type.startsWith("video/")) return "video";
  const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
  if (["opus", "amr", "m4a", "aac", "wav", "mp3", "ogg", "flac"].includes(ext)) return "audio";
  if (["mp4", "mov", "mkv", "webm", "3gp", "avi"].includes(ext)) return "video";
  if (["jpg", "jpeg", "png", "webp", "heic", "heif", "gif", "bmp", "tif", "tiff"].includes(ext)) return "image";
  return "other";
}

function IntakeZone({ caseId, onUploaded, compact }: { caseId: string; onUploaded: () => void; compact: boolean }) {
  const [files, setFiles] = useState<File[]>([]);
  const [role, setRole] = useState<EvidenceRole>("questioned");
  const [receivedFrom, setReceivedFrom] = useState("");
  const [description, setDescription] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const depth = useRef(0);
  const { push } = useToast();

  const add = useCallback((list: FileList | File[] | null) => {
    if (!list) return;
    const incoming = Array.from(list).filter((f) => f.size > 0);
    setFiles((cur) => {
      const seen = new Set(cur.map((f) => `${f.name}:${f.size}:${f.lastModified}`));
      return [...cur, ...incoming.filter((f) => !seen.has(`${f.name}:${f.size}:${f.lastModified}`))];
    });
    setResults(null);
    setError(null);
  }, []);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    depth.current = 0;
    setDrag(false);
    add(e.dataTransfer.files);
  };

  const submit = async () => {
    if (!files.length || busy) return;
    setBusy(true);
    setProgress(0);
    setError(null);
    try {
      const out = await uploadEvidence(caseId, files, { role, description, received_from: receivedFrom }, setProgress);
      setResults(out);
      setFiles([]);
      const dups = out.filter((r) => r.duplicate).length;
      push({
        tone: dups ? "warn" : "success",
        title: `${plural(out.length - dups, "exhibit")} sealed and queued`,
        body: dups ? `${plural(dups, "file")} already in this case (same SHA-256): not ingested twice.` : "Analysis has started on this workstation.",
      });
      onUploaded();
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : String(e);
      setError(msg);
      push({ tone: "error", title: "Intake failed", body: msg });
    } finally {
      setBusy(false);
    }
  };

  const total = files.reduce((a, f) => a + f.size, 0);
  const [open, setOpen] = useState(false);
  const expanded = !compact || open || files.length > 0 || drag || busy || (results !== null && results.length > 0) || error !== null;
  const dragProps = {
    onDragEnter: (e: DragEvent) => {
      e.preventDefault();
      depth.current += 1;
      setDrag(true);
    },
    onDragOver: (e: DragEvent) => e.preventDefault(),
    onDragLeave: () => {
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setDrag(false);
    },
    onDrop,
  };
  const fileInput = (
    <input
      ref={input}
      type="file"
      multiple
      accept={ACCEPT}
      className="hidden"
      onChange={(e) => {
        add(e.target.files);
        e.target.value = "";
      }}
    />
  );

  if (!expanded) {
    return (
      <div className="panel overflow-hidden p-2" {...dragProps}>
        {fileInput}
        <div className="flex items-center gap-4 rounded-xl border-2 border-dashed border-white/10 bg-ink-900/40 px-4 py-3 transition hover:border-accent/40">
          <button type="button" onClick={() => input.current?.click()} className="group flex min-w-0 flex-1 items-center gap-4 text-left">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 shadow-glow transition group-hover:scale-105">
              <UploadCloud className="h-5 w-5 text-accent" />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-white">
                Drop seized media here to add exhibits, or <span className="text-accent-soft underline underline-offset-4">browse files</span>
              </span>
              <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-2xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <Fingerprint className="h-3 w-3 text-accent/70" /> MD5 · SHA-1 · SHA-256 on the raw bytes
                </span>
                <span className="inline-flex items-center gap-1">
                  <Lock className="h-3 w-3 text-accent/70" /> stored write-once
                </span>
                <span className="inline-flex items-center gap-1">
                  <ShieldCheck className="h-3 w-3 text-accent/70" /> custody row per exhibit
                </span>
              </span>
            </span>
          </button>
          <button type="button" className="btn-secondary btn-sm shrink-0" onClick={() => setOpen(true)}>
            Intake form
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="panel overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="p-4" {...dragProps}>
          {fileInput}
          {files.length === 0 ? (
            <button
              type="button"
              onClick={() => input.current?.click()}
              className={cx(
                "group relative flex min-h-[208px] w-full flex-col items-center justify-center gap-3 overflow-hidden rounded-xl border-2 border-dashed px-6 py-8 text-center transition",
                drag ? "border-accent bg-accent/[0.08]" : "border-white/10 bg-ink-900/40 hover:border-accent/50 hover:bg-accent/[0.03]",
              )}
            >
              <div className="scan-grid opacity-40" />
              <motion.div
                animate={drag ? { scale: 1.12, y: -4 } : { scale: 1, y: 0 }}
                className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 shadow-glow"
              >
                <UploadCloud className="h-7 w-7 text-accent" />
              </motion.div>
              <div className="relative">
                <div className="text-base font-semibold text-white">{drag ? "Release to stage these files" : "Drop seized media here"}</div>
                <div className="mt-1 text-sm text-slate-400">
                  or <span className="text-accent-soft underline underline-offset-4">browse files</span> · images, voice notes,
                  call recordings, videos · up to 512 MB each
                </div>
              </div>
              <div className="relative mt-1 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-2xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <Fingerprint className="h-3.5 w-3.5 text-accent/70" /> MD5 · SHA-1 · SHA-256 on the raw bytes
                </span>
                <span className="inline-flex items-center gap-1">
                  <Lock className="h-3.5 w-3.5 text-accent/70" /> stored write-once
                </span>
                <span className="inline-flex items-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-accent/70" /> custody row per exhibit
                </span>
              </div>
            </button>
          ) : (
            <div className={cx("rounded-xl border p-3 transition", drag ? "border-accent bg-accent/[0.06]" : "border-white/[0.08] bg-ink-900/40")}>
              <div className="mb-2 flex items-center justify-between px-1">
                <div className="text-sm font-medium text-slate-200">
                  {plural(files.length, "file")} staged · <span className="font-mono text-slate-400">{formatBytes(total)}</span>
                </div>
                <div className="flex gap-1">
                  <button type="button" className="btn-ghost btn-sm" onClick={() => input.current?.click()} disabled={busy}>
                    <UploadCloud className="h-3.5 w-3.5" /> Add
                  </button>
                  <button type="button" className="btn-ghost btn-sm" onClick={() => setFiles([])} disabled={busy}>
                    <Trash2 className="h-3.5 w-3.5" /> Clear
                  </button>
                </div>
              </div>
              <ul className="max-h-[168px] space-y-1 overflow-y-auto pr-1">
                <AnimatePresence initial={false}>
                  {files.map((f) => (
                    <motion.li
                      key={`${f.name}:${f.size}:${f.lastModified}`}
                      layout
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 8 }}
                      className="flex items-center gap-3 rounded-lg bg-white/[0.03] px-3 py-2"
                    >
                      <MediaIcon kind={guessKind(f)} className="h-4 w-4 text-accent" />
                      <span className="min-w-0 flex-1 truncate text-sm text-slate-200">{f.name}</span>
                      <span className="font-mono text-2xs text-slate-500">{formatBytes(f.size)}</span>
                      <button
                        type="button"
                        className="text-slate-500 hover:text-slate-200 disabled:opacity-40"
                        disabled={busy}
                        onClick={() => setFiles((cur) => cur.filter((x) => x !== f))}
                        aria-label={`Remove ${f.name}`}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
              {busy && (
                <div className="mt-3 space-y-1.5 px-1">
                  <ProgressBar value={progress} indeterminate={progress >= 0.999} />
                  <div className="flex justify-between text-2xs text-slate-400">
                    <span>{progress < 0.999 ? "Transferring to the evidence store…" : "Hashing and sealing on the workstation…"}</span>
                    <span className="font-mono">{Math.round(progress * 100)}%</span>
                  </div>
                </div>
              )}
            </div>
          )}
          <AnimatePresence>
            {results && results.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 overflow-hidden rounded-xl border border-emerald-400/20 bg-emerald-500/[0.04]"
              >
                <div className="flex items-center justify-between px-3 pt-2.5">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-200">
                    <CheckCircle2 className="h-4 w-4" /> Intake receipt: hashes computed by the workstation
                  </div>
                  <button type="button" className="text-slate-500 hover:text-slate-200" onClick={() => setResults(null)} aria-label="Close receipt">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
                <ul className="space-y-1 p-2">
                  {results.map((r) => (
                    <li key={r.id} className="flex items-center gap-3 rounded-lg bg-ink-950/40 px-2.5 py-1.5">
                      <ExhibitBadge exhibit={r.exhibit} role={r.role} size="sm" />
                      <span className="min-w-0 max-w-[30%] truncate text-xs text-slate-300">{r.filename}</span>
                      <span className="min-w-0 flex-1 truncate font-mono text-2xs text-slate-400" title={r.sha256}>
                        SHA-256 {r.sha256}
                      </span>
                      {r.duplicate && (
                        <span className="chip border-amber-400/30 bg-amber-500/10 text-amber-200" title="Same SHA-256 already in this case">
                          <FileWarning className="h-3 w-3" /> duplicate
                        </span>
                      )}
                      <CopyButton text={r.sha256} />
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
          {error && <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</div>}
        </div>

        <div className="space-y-4 border-t hairline bg-ink-900/30 p-5 lg:border-l lg:border-t-0">
          <div>
            <div className="flex items-center justify-between">
              <div className="label">Exhibit role</div>
              {compact && !busy && (
                <button
                  type="button"
                  className="-mt-1.5 text-slate-500 hover:text-slate-200"
                  aria-label="Collapse intake"
                  onClick={() => {
                    setOpen(false);
                    setFiles([]);
                    setResults(null);
                    setError(null);
                  }}
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-1 rounded-lg border border-white/10 bg-ink-950/50 p-1">
              {(
                [
                  ["questioned", "Questioned", "Item under examination (Q)"],
                  ["reference", "Reference", "Known genuine sample (R)"],
                ] as const
              ).map(([v, label, hint]) => (
                <button
                  key={v}
                  type="button"
                  title={hint}
                  onClick={() => setRole(v)}
                  className={cx(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition",
                    role === v
                      ? v === "questioned"
                        ? "bg-cyan-500/20 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.4)]"
                        : "bg-violet-500/20 text-violet-100 shadow-[inset_0_0_0_1px_rgba(167,139,250,0.4)]"
                      : "text-slate-400 hover:text-slate-200",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="mt-1.5 text-2xs text-slate-500">
              {role === "questioned"
                ? "Marked Q1, Q2 … in the report."
                : "Marked R1, R2 … and used for comparison (same face, same speaker)."}
            </div>
          </div>
          <div>
            <label className="label" htmlFor="received-from">
              Received from
            </label>
            <input
              id="received-from"
              className="input"
              placeholder="IO, Cyber Crime PS (sealed pen drive)"
              value={receivedFrom}
              onChange={(e) => setReceivedFrom(e.target.value)}
              maxLength={500}
            />
          </div>
          <div>
            <label className="label" htmlFor="description">
              Description
            </label>
            <textarea
              id="description"
              className="input min-h-[64px] resize-y"
              placeholder="WhatsApp voice note demanding payment, received 21/10/2026"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
            />
          </div>
          <button type="button" className="btn-primary w-full" disabled={!files.length || busy} onClick={() => void submit()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Inbox className="h-4 w-4" />}
            {busy ? "Sealing exhibits…" : files.length ? `Seal & submit ${plural(files.length, "exhibit")}` : "Stage files to submit"}
          </button>
        </div>
      </div>
    </div>
  );
}

type Filter = "all" | "questioned" | "reference" | "flagged" | "pending";

export function ExhibitsTab({ view, onChanged }: { view: CaseView; onChanged: () => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const evidence = view.evidence;
  const counts: Record<Filter, number> = {
    all: evidence.length,
    questioned: evidence.filter((e) => e.role === "questioned").length,
    reference: evidence.filter((e) => e.role === "reference").length,
    flagged: evidence.filter((e) => isFlagged(e.verdict)).length,
    pending: evidence.filter((e) => isPending(e.status)).length,
  };
  const shown = useMemo(() => {
    const order = (x: string) => (x.startsWith("Q") ? 0 : 1);
    return evidence
      .filter((e) =>
        filter === "all"
          ? true
          : filter === "flagged"
            ? isFlagged(e.verdict)
            : filter === "pending"
              ? isPending(e.status)
              : e.role === filter,
      )
      .sort((a, b) => order(a.exhibit) - order(b.exhibit) || a.exhibit.localeCompare(b.exhibit, undefined, { numeric: true }));
  }, [evidence, filter]);

  // Browsers allow ~6 connections per host: stream the items being analysed first, then queued ones.
  const liveIds = useMemo(() => {
    const analysing = evidence.filter((e) => e.status === "analyzing").map((e) => e.id);
    const queued = evidence.filter((e) => e.status === "queued").map((e) => e.id);
    return new Set([...analysing, ...queued].slice(0, MAX_LIVE_STREAMS));
  }, [evidence]);

  return (
    <div className="space-y-5">
      <IntakeZone caseId={view.case.id} onUploaded={onChanged} compact={evidence.length > 0} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {(
            [
              ["all", "All"],
              ["questioned", "Questioned"],
              ["reference", "Reference"],
              ["flagged", "Flagged"],
              ["pending", "In analysis"],
            ] as [Filter, string][]
          ).map(([f, label]) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cx(
                "rounded-full border px-3 py-1 text-xs font-medium transition",
                filter === f
                  ? "border-accent/50 bg-accent/15 text-accent-soft"
                  : "border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-200",
              )}
            >
              {label} <span className="ml-1 font-mono opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5 text-2xs text-slate-500">
          <CopyIcon className="h-3 w-3" /> Click an exhibit for the full examination
        </div>
      </div>
      {shown.length === 0 ? (
        <div className="panel">
          <EmptyState
            title={evidence.length ? "No exhibits match this filter" : "No exhibits in this case yet"}
            body={
              evidence.length
                ? "Choose another filter above."
                : "Drop the seized files into the intake zone above. Each one is fingerprinted, sealed and analysed automatically."
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {shown.map((e, i) => (
            <EvidenceCard key={e.id} ev={e} live={liveIds.has(e.id)} index={i} onDone={onChanged} />
          ))}
        </div>
      )}
    </div>
  );
}
