#!/usr/bin/env node
/**
 * Screenshot every dashboard screen against a running backend (dev: `npm run dev`, which proxies
 * /lab/api to VITE_API, default http://127.0.0.1:8010).
 *
 *   node scripts/screenshots.mjs [--base http://127.0.0.1:5175/lab] [--out screenshots] [--full]
 *                                [--make-report] [--live auto|<evidence id>]
 *
 * --make-report generates a report through the UI when the case has none; --live re-analyses
 * an exhibit (default: the largest video) and captures the live scan on the detail page and the
 * case grid while it runs.
 * Exhibits are picked from the live data (no fixtures): the most interesting image / audio /
 * video exhibit of the first case that has them. Playwright is resolved with require() so a
 * globally installed copy works (no dependency in package.json).
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const args = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};
const BASE = arg("--base", "http://127.0.0.1:5175/lab").replace(/\/$/, "");
const OUT = resolve(arg("--out", "screenshots"));
const FULL = args.includes("--full");
const ONLY = arg("--only", "");
mkdirSync(OUT, { recursive: true });

const api = async (path, init) => {
  const r = await fetch(`${BASE}/api${path}`, init);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
};

const RANK = { SYNTHETIC: 5, MANIPULATED: 4, SUSPICIOUS: 3, INCONCLUSIVE: 1, NO_INDICATORS: 2 };
const IMAGE_RANK = { MANIPULATED: 6, SYNTHETIC: 5, SUSPICIOUS: 3, INCONCLUSIVE: 1, NO_INDICATORS: 2 };

async function pick() {
  const cases = await api("/cases");
  if (!cases.length) throw new Error("no cases on the backend");
  const views = await Promise.all(cases.map((c) => api(`/cases/${c.id}`)));
  const all = views.flatMap((v) => v.evidence.map((e) => ({ ...e, links: v.links.length })));
  const best = (kind, extra = () => 0, rank = RANK) =>
    all
      .filter((e) => e.kind === kind && e.status === "done")
      .sort((a, b) => (rank[b.verdict] ?? 0) + extra(b) - ((rank[a.verdict] ?? 0) + extra(a)))[0];
  const mainCase = [...views].sort((a, b) => b.links.length - a.links.length || b.evidence.length - a.evidence.length)[0];
  return {
    caseId: mainCase.case.id,
    image: best("image", () => 0, IMAGE_RANK),
    synthetic: all.find((e) => e.kind === "image" && e.verdict === "SYNTHETIC"),
    audio: best("audio", (e) => (e.filename.endsWith(".wav") ? 0.5 : 0)),
    video: best("video", (e) => (e.role === "questioned" ? 0.5 : 0)),
    largestVideo: all.filter((e) => e.kind === "video").sort((a, b) => b.size_bytes - a.size_bytes)[0],
  };
}

async function settle(page, ms = 1400) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(ms);
}

async function shot(page, name) {
  if (ONLY && !ONLY.split(",").includes(name)) return;
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: FULL });
  console.log("saved", path);
}

/** Scroll so the exhibit grid (just below the intake strip) fills the viewport. */
async function scrollToGrid(page) {
  await page.evaluate(() => {
    const strip = [...document.querySelectorAll("span")].find((s) => s.textContent?.startsWith("Drop seized media here"));
    const panel = strip?.closest(".panel");
    if (panel) window.scrollTo(0, panel.getBoundingClientRect().top + window.scrollY - 130);
    else window.scrollTo(0, 330);
  });
}

const run = async () => {
  const p = await pick();
  console.log("picked", JSON.stringify({ case: p.caseId, image: p.image?.id, audio: p.audio?.id, video: p.video?.id }));
  // The "new headless" channel includes Chrome's PDF viewer (for the report preview).
  const browser = await chromium.launch({ channel: "chromium" }).catch(() => chromium.launch());
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: "dark" });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.error("PAGE ERROR", e.message));
  page.on("console", (m) => m.type() === "error" && console.error("console:", m.text()));

  await page.goto(`${BASE}/`);
  await settle(page, 1800);
  await shot(page, "01-home");

  await page.goto(`${BASE}/cases/${p.caseId}`);
  await settle(page, 1800);
  await shot(page, "02-case-exhibits");
  await scrollToGrid(page);
  await page.waitForTimeout(900);
  await shot(page, "02b-case-exhibits-grid");

  if (p.image) {
    await page.goto(`${BASE}/evidence/${p.image.id}`);
    await settle(page, 2200);
    await shot(page, "03-evidence-image");
    // a closer look at the technique accordion and the compare slider
    const compare = page.getByRole("button", { name: /Compare/ });
    if (await compare.isEnabled().catch(() => false)) {
      await compare.click();
      await page.waitForTimeout(500);
      await shot(page, "03b-evidence-image-compare");
    }
    await page.evaluate(() => document.getElementById("tech-image.copymove")?.scrollIntoView({ block: "start" }));
    await page.waitForTimeout(800);
    await shot(page, "03c-evidence-image-techniques");
  }
  if (p.synthetic && p.synthetic.id !== p.image?.id) {
    await page.goto(`${BASE}/evidence/${p.synthetic.id}`);
    await settle(page, 2200);
    await shot(page, "03d-evidence-image-synthetic");
  }
  if (p.audio) {
    await page.goto(`${BASE}/evidence/${p.audio.id}`);
    await settle(page, 2200);
    await shot(page, "04-evidence-audio");
    await page.evaluate(() => window.scrollBy(0, 640));
    await page.waitForTimeout(700);
    await shot(page, "04b-evidence-audio-timeline");
  }
  if (p.video) {
    await page.goto(`${BASE}/evidence/${p.video.id}`);
    await settle(page, 2600);
    await shot(page, "05-evidence-video");
    await page.evaluate(() => window.scrollBy(0, 560));
    await page.waitForTimeout(700);
    await shot(page, "05b-evidence-video-timeline");
  }

  await page.goto(`${BASE}/cases/${p.caseId}/graph`);
  await settle(page, 2200);
  await shot(page, "06-provenance-graph");

  await page.goto(`${BASE}/cases/${p.caseId}/custody`);
  await settle(page, 2400);
  await shot(page, "07-chain-of-custody");

  await page.goto(`${BASE}/cases/${p.caseId}/reports`);
  await settle(page, 2000);
  const view = await api(`/cases/${p.caseId}`);
  if (!view.reports.length && args.includes("--make-report")) {
    await page.fill("#rep-examiner", "Dr. A. Rao");
    await page.fill("#rep-designation", "Scientific Officer (Cyber Forensics)");
    await page.getByRole("button", { name: /Generate court report/ }).click();
    await page.waitForSelector("iframe", { timeout: 120000 });
    await page.waitForTimeout(2500);
  }
  await shot(page, "08-reports");

  const liveArg = arg("--live", "");
  if (liveArg) {
    const target = liveArg === "auto" ? p.largestVideo : { id: liveArg };
    if (target?.id) {
      const ev = (await api(`/evidence/${target.id}`)).evidence;
      await api(`/evidence/${ev.id}/reanalyze`, { method: "POST" });
      await page.goto(`${BASE}/evidence/${ev.id}`);
      await page.waitForTimeout(Number(arg("--live-wait", "9000")));
      await shot(page, "10-live-scan-detail");
      await page.goto(`${BASE}/cases/${ev.case_id}`);
      await page.waitForTimeout(2500);
      await scrollToGrid(page);
      await page.waitForTimeout(1500);
      await shot(page, "09-live-scan-case");
    }
  }

  await browser.close();
};

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
