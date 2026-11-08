import {
  Background,
  BackgroundVariant,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  getStraightPath,
  ReactFlow,
  useInternalNode,
  type Edge,
  type EdgeProps,
  type InternalNode,
  type Node,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, GitCompareArrows, MousePointerClick, Network } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { urls, type CaseView, type EvidenceLink, type LabEvidence } from "../../api";
import { Lightbox, type LightboxItem } from "../../components/Modal";
import { cx, EmptyState, ExhibitBadge, MediaIcon, SafeImg, ToneBadge } from "../../components/ui";
import { formatPercent } from "../../lib/format";
import { groupLinks, linkMeta, LINK_META, type LinkGroup } from "../../lib/links";
import { circleLayout } from "../../lib/layout";
import { thumbUrl } from "../../lib/media";
import { evidenceMeta } from "../../lib/verdict";

// ------------------------------------------------------------------ nodes

type ExhibitNodeData = { ev: LabEvidence; dim: boolean; active: boolean };
type ExhibitNode = Node<ExhibitNodeData, "exhibit">;

function ExhibitNodeView({ data }: NodeProps<ExhibitNode>) {
  const { ev, dim, active } = data;
  const meta = evidenceMeta(ev);
  return (
    <div
      className={cx(
        "w-[188px] overflow-hidden rounded-xl border bg-ink-850/95 backdrop-blur transition duration-200",
        dim && "opacity-35",
      )}
      style={{
        borderColor: active ? meta.hex : `${meta.hex}66`,
        boxShadow: active ? `0 0 0 1px ${meta.hex}, 0 0 32px -6px ${meta.hex}` : `0 0 28px -12px ${meta.hex}`,
      }}
    >
      <Handle type="target" position={Position.Top} className="!h-1 !w-1 !border-0 !bg-transparent" isConnectable={false} />
      <Handle type="source" position={Position.Bottom} className="!h-1 !w-1 !border-0 !bg-transparent" isConnectable={false} />
      <div className="relative h-[92px] bg-ink-900">
        <SafeImg
          src={thumbUrl(ev)}
          alt={ev.filename}
          className="h-full w-full object-cover"
          draggable={false}
          fallback={
            <div className="flex h-full w-full items-center justify-center text-slate-600">
              <MediaIcon kind={ev.kind} className="h-8 w-8" />
            </div>
          }
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950/80 to-transparent" />
        <ExhibitBadge exhibit={ev.exhibit} role={ev.role} size="sm" className="absolute left-2 top-2" />
        {ev.risk_index !== null && (
          <span className="absolute right-2 top-2 rounded bg-ink-950/80 px-1.5 py-0.5 font-mono text-[10px] text-slate-200">risk {ev.risk_index}</span>
        )}
      </div>
      <div className="space-y-1.5 px-2.5 py-2">
        <div className="flex items-center gap-1.5 text-xs font-medium text-slate-100" title={ev.filename}>
          <MediaIcon kind={ev.kind} className="h-3.5 w-3.5 shrink-0 text-slate-500" />
          <span className="truncate">{ev.filename}</span>
        </div>
        <ToneBadge meta={meta} size="sm" />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ floating edges

type LinkEdgeData = { group: LinkGroup; selected: boolean; dim: boolean };
type LinkEdge = Edge<LinkEdgeData, "link">;

function center(n: InternalNode) {
  const w = n.measured.width ?? 188;
  const h = n.measured.height ?? 150;
  return { x: n.internals.positionAbsolute.x + w / 2, y: n.internals.positionAbsolute.y + h / 2, w: w / 2, h: h / 2 };
}

/** Where the line between two node centres leaves node `a`'s rectangle. */
function borderPoint(a: InternalNode, b: InternalNode) {
  const ca = center(a);
  const cb = center(b);
  const dx = cb.x - ca.x;
  const dy = cb.y - ca.y;
  if (dx === 0 && dy === 0) return { x: ca.x, y: ca.y };
  const sx = ca.w / Math.abs(dx || 1e-9);
  const sy = ca.h / Math.abs(dy || 1e-9);
  const s = Math.min(sx, sy);
  return { x: ca.x + dx * s, y: ca.y + dy * s };
}

function LinkEdgeView({ id, source, target, data }: EdgeProps<LinkEdge>) {
  const s = useInternalNode(source);
  const t = useInternalNode(target);
  if (!s || !t || !data) return null;
  const p1 = borderPoint(s, t);
  const p2 = borderPoint(t, s);
  const [path, lx, ly] = getStraightPath({ sourceX: p1.x, sourceY: p1.y, targetX: p2.x, targetY: p2.y });
  const top = data.group.links[0];
  const topMeta = linkMeta(top?.kind ?? "");
  const color = topMeta.hex;
  const width = 1.5 + 2.5 * Math.max(0, Math.min(1, top?.score ?? 0));
  return (
    <>
      <BaseEdge
        id={`${id}-glow`}
        path={path}
        style={{ stroke: color, strokeOpacity: data.selected ? 0.35 : 0.12, strokeWidth: width + 8, transition: "all .2s" }}
      />
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: color,
          strokeWidth: width,
          strokeOpacity: data.dim ? 0.2 : 0.95,
          strokeDasharray: topMeta.dash,
          strokeLinecap: "round",
          transition: "all .2s",
        }}
        interactionWidth={24}
      />
      <EdgeLabelRenderer>
        <div
          className={cx("nodrag nopan absolute flex flex-col items-center gap-1", data.dim && "opacity-30")}
          style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)`, pointerEvents: "all" }}
        >
          {data.group.links.map((l) => {
            const m = linkMeta(l.kind);
            return (
              <span
                key={l.kind}
                className={cx(
                  "inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border bg-ink-950/90 px-2 py-0.5 text-[10px] font-semibold text-slate-200 backdrop-blur",
                  data.selected && "ring-1 ring-white/40",
                )}
                style={{ borderColor: `${m.hex}aa` }}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: m.hex }} />
                {m.label} <span className="font-mono text-slate-400">{l.score.toFixed(2)}</span>
              </span>
            );
          })}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const nodeTypes = { exhibit: ExhibitNodeView };
const edgeTypes = { link: LinkEdgeView };

// ------------------------------------------------------------------ layout

// ------------------------------------------------------------------ side panel

function LinkDetail({
  group,
  byId,
  onArtifact,
}: {
  group: LinkGroup;
  byId: Map<string, LabEvidence>;
  onArtifact: (items: LightboxItem[], i: number) => void;
}) {
  const a = byId.get(group.a);
  const b = byId.get(group.b);
  const exhibitOf = (id: string) => byId.get(id)?.exhibit ?? id;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        {[a, b].map((ev, i) =>
          ev ? (
            <Link key={ev.id} to={`/evidence/${ev.id}`} className={cx("group block", i === 1 && "col-start-3")}>
              <div className="relative aspect-video overflow-hidden rounded-lg border border-white/10 bg-ink-900">
                <SafeImg src={thumbUrl(ev)} alt={ev.filename} className="h-full w-full object-cover" fallback={<div className="flex h-full items-center justify-center text-slate-600"><MediaIcon kind={ev.kind} className="h-6 w-6" /></div>} />
                <ExhibitBadge exhibit={ev.exhibit} role={ev.role} size="sm" className="absolute left-1.5 top-1.5" />
              </div>
              <div className="mt-1 truncate text-2xs text-slate-400 group-hover:text-accent-soft">{ev.filename}</div>
            </Link>
          ) : (
            <div key={i} className="text-xs text-slate-500">
              unknown exhibit
            </div>
          ),
        )}
        <GitCompareArrows className="col-start-2 row-start-1 h-5 w-5 text-slate-500" />
      </div>
      {group.links.map((l: EvidenceLink) => {
        const m = linkMeta(l.kind);
        const items: LightboxItem[] = l.artifacts.map((name) => ({
          src: urls.artifact(l.source, name),
          title: `${m.label}: ${exhibitOf(l.source)} vs ${exhibitOf(l.target)}`,
          caption: l.detail,
          meta: name,
        }));
        return (
          <div key={l.kind} className="rounded-xl border bg-ink-900/50 p-3.5" style={{ borderColor: `${m.hex}40` }}>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-100">
                <span className="h-2 w-2 rounded-full" style={{ background: m.hex }} />
                {m.label}
              </span>
              <span className="font-mono text-xs text-slate-300">score {l.score.toFixed(3)}</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
              <motion.div
                className="h-full rounded-full"
                style={{ background: m.hex }}
                initial={{ width: 0 }}
                animate={{ width: formatPercent(Math.max(0, Math.min(1, l.score)), 1) }}
                transition={{ duration: 0.6 }}
              />
            </div>
            <p className="mt-2.5 text-sm leading-relaxed text-slate-300">{l.detail}</p>
            <div className="mt-1 text-2xs text-slate-500">
              computed from {exhibitOf(l.source)} → {exhibitOf(l.target)} · {m.blurb}
            </div>
            {items.length > 0 && (
              <div className="mt-3 space-y-2">
                {items.map((it, i) => (
                  <button key={it.src} type="button" onClick={() => onArtifact(items, i)} className="group block w-full overflow-hidden rounded-lg border border-white/10 bg-ink-950">
                    <SafeImg
                      src={it.src}
                      alt={it.title}
                      className="w-full object-contain transition group-hover:opacity-90"
                      fallback={<div className="p-4 text-2xs text-slate-500">Comparison figure not available.</div>}
                    />
                    <div className="px-2 py-1 text-left text-2xs text-slate-500">
                      Aligned comparison: original · aligned · difference (click to enlarge)
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ tab

export function GraphTab({ view }: { view: CaseView }) {
  const navigate = useNavigate();
  const groups = useMemo(() => groupLinks(view.links), [view.links]);
  const byId = useMemo(() => new Map(view.evidence.map((e) => [e.id, e])), [view.evidence]);
  const [selected, setSelected] = useState<string | null>(groups[0]?.key ?? null);
  const [focusNode, setFocusNode] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<{ items: LightboxItem[]; index: number } | null>(null);
  const positions = useMemo(() => circleLayout(view.evidence), [view.evidence]);
  const sel = groups.find((g) => g.key === selected) ?? null;

  const neighbours = useMemo(() => {
    if (!focusNode) return null;
    const s = new Set<string>([focusNode]);
    for (const g of groups) if (g.a === focusNode || g.b === focusNode) s.add(g.a === focusNode ? g.b : g.a);
    return s;
  }, [focusNode, groups]);

  const nodes: ExhibitNode[] = useMemo(
    () =>
      view.evidence.map((ev) => ({
        id: ev.id,
        type: "exhibit" as const,
        position: positions[ev.id] ?? { x: 0, y: 0 },
        data: {
          ev,
          dim: neighbours !== null && !neighbours.has(ev.id),
          active: focusNode === ev.id || (sel !== null && (sel.a === ev.id || sel.b === ev.id)),
        },
      })),
    [view.evidence, positions, neighbours, focusNode, sel],
  );
  const edges: LinkEdge[] = useMemo(
    () =>
      groups
        .filter((g) => byId.has(g.a) && byId.has(g.b))
        .map((g) => ({
          id: g.key,
          source: g.a,
          target: g.b,
          type: "link" as const,
          data: {
            group: g,
            selected: g.key === selected,
            dim: neighbours !== null && !(neighbours.has(g.a) && neighbours.has(g.b)),
          },
        })),
    [groups, byId, selected, neighbours],
  );

  if (view.evidence.length === 0) {
    return (
      <div className="panel">
        <EmptyState title="No exhibits yet" body="Add exhibits to the case: the graph links them by shared content, faces, voices, devices and generators." />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="panel flex h-[680px] flex-col overflow-hidden">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b hairline px-4 py-2.5">
          <span className="eyebrow">Relationships</span>
          {Object.entries(LINK_META).map(([k, m]) => (
            <span key={k} className="inline-flex items-center gap-1.5 text-2xs text-slate-300">
              <svg width="22" height="6" aria-hidden="true">
                <line
                  x1="1"
                  y1="3"
                  x2="21"
                  y2="3"
                  stroke={m.hex}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeDasharray={m.dash ? m.dash.split(" ").map((x) => String(Number(x) * 0.6)).join(" ") : undefined}
                />
              </svg>
              {m.label}
            </span>
          ))}
        </div>
        <div className="relative min-h-0 flex-1">
          <ReactFlow<ExhibitNode, LinkEdge>
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            colorMode="dark"
            fitView
            fitViewOptions={{ padding: 0.08 }}
            minZoom={0.3}
            maxZoom={1.8}
            nodesConnectable={false}
            proOptions={{ hideAttribution: true }}
            onEdgeClick={(_, e) => {
              setSelected(e.id);
              setFocusNode(null);
            }}
            onNodeClick={(_, n) => setFocusNode((f) => (f === n.id ? null : n.id))}
            onNodeDoubleClick={(_, n) => navigate(`/evidence/${n.id}`)}
            onPaneClick={() => setFocusNode(null)}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="rgba(148,163,184,0.18)" />
            <Controls showInteractive={false} position="bottom-left" />
  
          </ReactFlow>
        </div>
      </div>

      <div className="panel flex max-h-[680px] flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b hairline px-5 py-3.5">
          <h3 className="panel-title">
            <Network className="h-4 w-4 text-accent" /> Link evidence
          </h3>
          <span className="inline-flex items-center gap-1 text-2xs text-slate-500">
            <MousePointerClick className="h-3 w-3" /> click an edge · {groups.length} pairs
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {groups.length === 0 ? (
            <EmptyState
              mascot={false}
              title="No relationships found"
              body="No two exhibits share content, a face, a voice, a device or a generator signature (or analysis is still running)."
            />
          ) : (
            <>
              <div className="mb-4 flex flex-wrap gap-1.5">
                {groups.map((g) => (
                  <button
                    key={g.key}
                    type="button"
                    onClick={() => {
                      setSelected(g.key);
                      setFocusNode(null);
                    }}
                    className={cx(
                      "rounded-lg border px-2 py-1 font-mono text-2xs transition",
                      g.key === selected ? "border-accent/50 bg-accent/15 text-accent-soft" : "border-white/10 text-slate-400 hover:text-slate-200",
                    )}
                  >
                    {byId.get(g.a)?.exhibit ?? "?"} ↔ {byId.get(g.b)?.exhibit ?? "?"}
                  </button>
                ))}
              </div>
              <AnimatePresence mode="wait">
                {sel ? (
                  <motion.div key={sel.key} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}>
                    <LinkDetail group={sel} byId={byId} onArtifact={(items, index) => setLightbox({ items, index })} />
                  </motion.div>
                ) : (
                  <div className="text-sm text-slate-500">Select a pair to see how the exhibits are related.</div>
                )}
              </AnimatePresence>
            </>
          )}
          {focusNode && byId.get(focusNode) && (
            <Link to={`/evidence/${focusNode}`} className="btn-secondary btn-sm mt-4 w-full">
              Open {byId.get(focusNode)?.exhibit} <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          )}
        </div>
      </div>
      <Lightbox
        items={lightbox?.items ?? []}
        index={lightbox?.index ?? null}
        onIndex={(i) => setLightbox((l) => (l ? { ...l, index: i } : l))}
        onClose={() => setLightbox(null)}
      />
    </div>
  );
}
