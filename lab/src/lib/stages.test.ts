import { describe, expect, it } from "vitest";
import type { ProgressEvent, TechniqueInfo } from "../api";
import {
  activeStage,
  buildStageRows,
  currentRun,
  expectedTechniques,
  indexTechniques,
  isDone,
  overallProgress,
  stageLabel,
} from "./stages";

const TECHS: TechniqueInfo[] = [
  { id: "image.ela", name: "Error Level Analysis", category: "tampering", kinds: ["image"], method: "", reference: null, limitations: null },
  { id: "image.aigen", name: "AI-generated image classifier", category: "synthetic", kinds: ["image"], method: "", reference: null, limitations: null },
  { id: "audio.voice", name: "Synthetic / cloned voice detector", category: "synthetic", kinds: ["audio", "video"], method: "", reference: null, limitations: null },
  { id: "video.deepfake", name: "Deepfake face timeline", category: "synthetic", kinds: ["video"], method: "", reference: null, limitations: null },
];
const IDX = indexTechniques(TECHS);

let clock = Date.parse("2026-11-07T17:49:10.000Z");
function ev(stage: string, status: string, message = "", progress = 0): ProgressEvent {
  clock += 250;
  return { evidence_id: "ev_1", stage, status, message, progress, at: new Date(clock).toISOString() };
}

describe("stage labels", () => {
  it("names technique stages from GET /techniques", () => {
    expect(stageLabel("image.ela", IDX)).toBe("Error Level Analysis");
    expect(stageLabel("video.deepfake", IDX)).toBe("Deepfake face timeline");
  });

  it("names pipeline stages", () => {
    expect(stageLabel("intake", IDX)).toBe("Evidence received & fingerprinted");
    expect(stageLabel("integrity", IDX)).toBe("Integrity re-verified");
    expect(stageLabel("links", IDX)).toBe("Cross-exhibit comparison");
    expect(stageLabel("done", IDX)).toBe("Analysis complete");
  });

  it("humanises unknown stages instead of dropping them", () => {
    expect(stageLabel("image.new_thing", IDX)).toBe("Image new thing");
    expect(stageLabel("", IDX)).toBe("Stage");
  });

  it("lists the techniques expected for a media kind", () => {
    expect(expectedTechniques(TECHS, "image")).toEqual(["image.ela", "image.aigen"]);
    expect(expectedTechniques(TECHS, "video")).toEqual(["audio.voice", "video.deepfake"]);
    expect(expectedTechniques(null, "audio")).toEqual([]);
  });
});

describe("checklist rows", () => {
  const run = [
    ev("intake", "ok", "received a.jpg: SHA-256 36eb…", 0),
    ev("queue", "running", "queued for analysis", 0),
    ev("integrity", "ok", "SHA-256 re-verified", 0.01),
    ev("image.ela", "running", "Error Level Analysis…", 0.02),
    ev("image.ela", "ok", "error level consistent with texture", 0.5),
    ev("image.aigen", "running", "AI-generated image classifier…", 0.5),
  ];

  it("keeps first-seen order, closes the queue row and marks the running technique", () => {
    const rows = buildStageRows(run, IDX, ["image.ela", "image.aigen"]);
    expect(rows.map((r) => [r.stage, r.status])).toEqual([
      ["intake", "ok"],
      ["queue", "ok"],
      ["integrity", "ok"],
      ["image.ela", "ok"],
      ["image.aigen", "running"],
    ]);
    const ela = rows.find((r) => r.stage === "image.ela");
    expect(ela?.message).toBe("error level consistent with texture");
    expect(ela?.durationMs).toBe(250);
    expect(ela?.isTechnique).toBe(true);
    expect(ela?.category).toBe("tampering");
  });

  it("shows not-yet-started techniques as pending", () => {
    const rows = buildStageRows(run.slice(0, 3), IDX, ["image.ela", "image.aigen"]);
    expect(rows.filter((r) => r.status === "pending").map((r) => r.stage)).toEqual(["image.ela", "image.aigen"]);
  });

  it("parses live sub-progress messages", () => {
    const rows = buildStageRows(
      [ev("video.deepfake", "running", "Deepfake face timeline…", 0.5), ev("video.deepfake", "running", "face model at 3s / 10s", 0.3)],
      IDX,
    );
    expect(rows[0]?.message).toBe("face model at 3s / 10s");
    expect(rows[0]?.sub).toBeCloseTo(0.3);
  });

  it("closes everything on done and drops pending rows", () => {
    const rows = buildStageRows([...run, ev("image.aigen", "skipped", "image too small"), ev("links", "running", "comparing"), ev("done", "done", "Manipulated image", 1)], IDX, [
      "image.ela",
      "image.aigen",
      "video.deepfake",
    ]);
    expect(rows.some((r) => r.status === "running" || r.status === "pending")).toBe(false);
    expect(rows.find((r) => r.stage === "image.aigen")?.status).toBe("skipped");
    expect(isDone([...run, ev("done", "done")])).toBe(true);
  });

  it("marks the running technique as failed when the analysis errors", () => {
    const rows = buildStageRows([...run, ev("done", "error", "analysis failed: boom", 1)], IDX);
    expect(rows.find((r) => r.stage === "image.aigen")?.status).toBe("error");
  });
});

describe("runs and progress", () => {
  it("keeps only the latest run after a re-analysis (plus the intake row)", () => {
    const first = [ev("intake", "ok"), ev("queue", "running"), ev("image.ela", "ok", "x", 0.5), ev("done", "done", "", 1)];
    const second = [ev("queue", "running"), ev("integrity", "ok", "", 0.01)];
    const run = currentRun([...first, ...second]);
    expect(run.map((e) => e.stage)).toEqual(["intake", "queue", "integrity"]);
    expect(isDone([...first, ...second])).toBe(false);
  });

  it("reports monotonic overall progress", () => {
    const events = [ev("image.ela", "running", "", 0.5), ev("video.deepfake", "running", "face model at 1s / 10s", 0.1)];
    expect(overallProgress(events)).toBe(0.5);
    expect(overallProgress([...events, ev("done", "done", "", 1)])).toBe(1);
    expect(overallProgress([])).toBe(0);
  });

  it("names the active stage for compact cards", () => {
    expect(activeStage([ev("image.ela", "running", "Error Level Analysis…")], IDX)?.label).toBe("Error Level Analysis");
    expect(activeStage([], IDX)).toBeNull();
  });
});
