import { Clapperboard, Film, Maximize2, ScanFace } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { urls, type EvidenceAnalysis, type LabEvidence } from "../../api";
import { ChartFrame, LegendSwatch, TimeLineChart, TONE_HI, TONE_LO, WindowScoreChart, type Marker } from "../../components/charts";
import { Lightbox, type LightboxItem } from "../../components/Modal";
import { SafeImg } from "../../components/ui";
import { arr, findTechnique, num, numArray, obj, str } from "../../lib/media";
import { audioBands, EnfChart, Spectrogram, SpliceChart, Transcript, Transport, VoiceChart } from "./AudioParts";

/** Current time / duration / playing of a media element, smooth (rAF) while playing. */
export function useMediaClock(ref: RefObject<HTMLMediaElement>, fallbackDuration: number | null | undefined) {
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(fallbackDuration ?? 0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    const m = ref.current;
    if (!m) return;
    let raf = 0;
    const tick = () => {
      setCurrent(m.currentTime);
      if (!m.paused) raf = requestAnimationFrame(tick);
    };
    const onPlay = () => {
      setPlaying(true);
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      setCurrent(m.currentTime);
    };
    const onMeta = () => {
      if (Number.isFinite(m.duration) && m.duration > 0) setDuration(m.duration);
    };
    const onTime = () => setCurrent(m.currentTime);
    m.addEventListener("play", onPlay);
    m.addEventListener("pause", onPause);
    m.addEventListener("ended", onPause);
    m.addEventListener("loadedmetadata", onMeta);
    m.addEventListener("durationchange", onMeta);
    m.addEventListener("timeupdate", onTime);
    m.addEventListener("seeked", onTime);
    onMeta();
    return () => {
      cancelAnimationFrame(raf);
      m.removeEventListener("play", onPlay);
      m.removeEventListener("pause", onPause);
      m.removeEventListener("ended", onPause);
      m.removeEventListener("loadedmetadata", onMeta);
      m.removeEventListener("durationchange", onMeta);
      m.removeEventListener("timeupdate", onTime);
      m.removeEventListener("seeked", onTime);
    };
  }, [ref]);
  useEffect(() => {
    if (fallbackDuration && !duration) setDuration(fallbackDuration);
  }, [fallbackDuration, duration]);
  const seek = useCallback(
    (t: number) => {
      const m = ref.current;
      if (!m) return;
      m.currentTime = Math.max(0, Math.min(t, Number.isFinite(m.duration) ? m.duration : t));
      setCurrent(m.currentTime);
    },
    [ref],
  );
  return { current, duration, playing, seek };
}

/** Spectrogram, voice, ENF, splice and transcript: shared by the audio and video viewers. */
function AudioTrack({
  ev,
  analysis,
  current,
  duration,
  seek,
}: {
  ev: LabEvidence;
  analysis: EvidenceAnalysis | null;
  current: number;
  duration: number;
  seek: (t: number) => void;
}) {
  const spectral = findTechnique(analysis, "audio.spectral");
  const spec = spectral?.artifacts.find((a) => a.kind === "spectrogram");
  const enf = findTechnique(analysis, "audio.enf");
  const showEnf = enf && (enf.status === "ok" || arr(enf.data.jumps).length > 0);
  return (
    <div className="space-y-4">
      {spec && spectral?.status === "ok" && (
        <Spectrogram
          evidenceId={ev.id}
          name={spec.name}
          duration={duration || num(spectral.data.duration_s) || 1}
          cursor={current}
          onSeek={seek}
          bands={audioBands(analysis)}
          maxHz={num(spectral.data.max_hz)}
          caption={spec.caption}
        />
      )}
      <VoiceChart t={findTechnique(analysis, "audio.voice")} duration={duration} cursor={current} onSeek={seek} />
      {showEnf && <EnfChart t={enf} cursor={current} onSeek={seek} />}
      <SpliceChart t={findTechnique(analysis, "audio.splice")} cursor={current} onSeek={seek} />
      <Transcript t={findTechnique(analysis, "audio.transcript")} cursor={current} onSeek={seek} />
    </div>
  );
}

export function AudioViewer({ ev, analysis }: { ev: LabEvidence; analysis: EvidenceAnalysis | null }) {
  const ref = useRef<HTMLAudioElement>(null);
  const { current, duration, playing, seek } = useMediaClock(ref, analysis?.media.duration_s);
  const play = useCallback(
    (t: number) => {
      seek(t);
      void ref.current?.play().catch(() => undefined);
    },
    [seek],
  );
  return (
    <div className="space-y-4">
      <audio ref={ref} src={urls.file(ev.id)} preload="metadata" />
      <div className="rounded-xl border border-white/[0.08] bg-ink-950/50 p-3">
        <Transport media={ref} current={current} duration={duration} playing={playing} />
      </div>
      <AudioTrack ev={ev} analysis={analysis} current={current} duration={duration} seek={play} />
    </div>
  );
}

export function VideoViewer({ ev, analysis }: { ev: LabEvidence; analysis: EvidenceAnalysis | null }) {
  const ref = useRef<HTMLVideoElement>(null);
  const { current, duration, seek } = useMediaClock(ref, analysis?.media.duration_s);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const play = useCallback(
    (t: number) => {
      seek(t);
      ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    },
    [seek],
  );

  const deepfake = findTechnique(analysis, "video.deepfake");
  const frames = findTechnique(analysis, "video.frames");
  const windows = arr(deepfake?.data.windows)
    .map((w) => obj(w))
    .filter((w): w is Record<string, unknown> => w !== null)
    .map((w) => ({ start: num(w.start) ?? 0, end: num(w.end) ?? 0, score: num(w.score), cues: arr(w.cues).map(String) }));
  const tauHi = num(deepfake?.data.tau_hi);
  const tauLo = num(deepfake?.data.tau_lo);
  const crops = arr(deepfake?.data.crop_logits)
    .map((c) => obj(c))
    .filter((c): c is Record<string, unknown> => c !== null)
    .map((c) => ({ t: num(c.t) ?? 0, logit: num(c.logit) ?? 0 }));

  const motionT = numArray(frames?.data.t);
  const motion = numArray(frames?.data.motion);
  const markers: Marker[] = [
    ...numArray(frames?.data.cuts_s).map((t) => ({ t, color: TONE_LO, label: "hard cut" })),
    ...numArray(frames?.data.duplicates_s).map((t) => ({ t, color: "#a78bfa", label: "duplicated frame" })),
    ...arr(frames?.data.gaps)
      .map((g) => obj(g))
      .filter((g): g is Record<string, unknown> => g !== null)
      .map((g) => ({ t: num(g.t) ?? 0, color: TONE_HI, label: `timestamp gap ${num(g.ms)?.toFixed(0) ?? "?"} ms` })),
  ];

  const gallery: LightboxItem[] = [];
  for (const t of [frames, deepfake]) {
    for (const a of t?.artifacts ?? []) gallery.push({ src: urls.artifact(ev.id, a.name), title: a.title, caption: a.caption, meta: a.name });
  }
  const faceArt = deepfake?.artifacts.find((a) => a.kind === "crop");
  const sheet = frames?.artifacts.find((a) => a.name.startsWith("contact_sheet"));
  const hasAudio = analysis?.media.has_audio !== false;

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-black">
        <video ref={ref} src={urls.file(ev.id)} controls playsInline preload="metadata" className="mx-auto block max-h-[460px] w-full bg-black" />
      </div>

      {windows.length > 0 && (
        <ChartFrame
          title={
            <span className="inline-flex items-center gap-1.5">
              <ScanFace className="h-3.5 w-3.5 text-accent" /> Deepfake face timeline (window score)
            </span>
          }
          right={<span className="font-mono text-2xs text-slate-500">{str(deepfake?.data.label) ?? ""} · {num(deepfake?.data.usable_windows) ?? 0} usable windows</span>}
          legend={
            <>
              <LegendSwatch color="#22d3ee" label="window score" />
              {tauHi !== null && <LegendSwatch color={TONE_HI} label={`strict ${tauHi.toFixed(3)} (1% of real windows)`} dashed />}
              {tauLo !== null && <LegendSwatch color={TONE_LO} label={`lenient ${tauLo.toFixed(3)} (5%)`} dashed />}
            </>
          }
          caption={`${str(deepfake?.data.benchmark) ?? ""}${str(deepfake?.data.benchmark) ? ". " : ""}Click a window to jump the video there.`}
          height={200}
        >
          <WindowScoreChart windows={windows} tauHi={tauHi} tauLo={tauLo} duration={duration} cursor={current} onSeek={play} yLabel="P(deepfake)" />
        </ChartFrame>
      )}

      {motionT.length > 1 && (
        <ChartFrame
          title={
            <span className="inline-flex items-center gap-1.5">
              <Film className="h-3.5 w-3.5 text-accent" /> Frame-to-frame motion
            </span>
          }
          right={
            <span className="font-mono text-2xs text-slate-500">
              {num(frames?.data.frames) ?? "?"} frames · {num(frames?.data.median_interval_ms)?.toFixed(1) ?? "?"} ms median interval
            </span>
          }
          legend={
            <>
              <LegendSwatch color="#38bdf8" label="mean pixel change" />
              <LegendSwatch color={TONE_LO} label="hard cut" dashed />
              <LegendSwatch color="#a78bfa" label="duplicated frame" dashed />
              <LegendSwatch color={TONE_HI} label="timestamp gap" dashed />
            </>
          }
          caption={markers.length ? `${markers.length} marker(s): click the chart to inspect that moment.` : "No cuts, duplicated frames or timestamp gaps: a continuous recording."}
          height={150}
        >
          <TimeLineChart t={motionT} y={motion} color="#38bdf8" markers={markers} cursor={current} onSeek={play} yFormat={(v) => v.toFixed(1)} yLabel="motion" />
        </ChartFrame>
      )}

      {(faceArt || sheet) && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {faceArt && (
            <figure className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
              <figcaption className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-200">
                <span className="inline-flex items-center gap-1.5">
                  <ScanFace className="h-3.5 w-3.5 text-accent" /> {faceArt.title}
                </span>
                <button type="button" className="text-slate-500 hover:text-white" onClick={() => setLightbox(gallery.findIndex((g) => g.meta === faceArt.name))}>
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              </figcaption>
              <button type="button" className="block w-full" onClick={() => setLightbox(gallery.findIndex((g) => g.meta === faceArt.name))}>
                <SafeImg src={urls.artifact(ev.id, faceArt.name)} alt={faceArt.title} className="w-full rounded-md" />
              </button>
              {crops.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {crops.map((c) => (
                    <button key={c.t} type="button" onClick={() => play(c.t)} className="rounded border border-white/10 px-1.5 py-0.5 font-mono text-2xs text-slate-400 hover:border-accent/40 hover:text-white">
                      {c.t.toFixed(1)}s · logit {c.logit.toFixed(2)}
                    </button>
                  ))}
                </div>
              )}
            </figure>
          )}
          {sheet && (
            <figure className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
              <figcaption className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-200">
                <span className="inline-flex items-center gap-1.5">
                  <Clapperboard className="h-3.5 w-3.5 text-accent" /> Contact sheet
                </span>
                <button type="button" className="text-slate-500 hover:text-white" onClick={() => setLightbox(gallery.findIndex((g) => g.meta === sheet.name))}>
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              </figcaption>
              <button type="button" className="block w-full" onClick={() => setLightbox(gallery.findIndex((g) => g.meta === sheet.name))}>
                <SafeImg src={urls.artifact(ev.id, sheet.name)} alt="Contact sheet" className="max-h-[220px] w-full rounded-md object-contain" />
              </button>
              <div className="mt-2 text-2xs text-slate-500">{sheet.caption}</div>
            </figure>
          )}
        </div>
      )}

      {hasAudio && (
        <div className="space-y-4 border-t hairline pt-4">
          <div className="eyebrow">Audio track</div>
          <AudioTrack ev={ev} analysis={analysis} current={current} duration={duration} seek={play} />
        </div>
      )}
      <Lightbox items={gallery} index={lightbox !== null && lightbox >= 0 ? lightbox : null} onIndex={setLightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
