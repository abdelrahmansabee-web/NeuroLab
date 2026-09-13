import React, { useRef, useState, useEffect, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import { Play, Pause, Maximize, Minimize2, ChevronLeft, ChevronRight, Circle, Square, X } from "lucide-react";
import {
  computeLiveTremorPower,
  formatTremorPower,
  resolveTremorMetrics,
} from "./tremorMetrics";
import {
  buildPinchEvidenceLines,
  buildTremorEvidenceLines,
  drawEvidenceCard,
  localTremorActivity,
  localTremorEnvelopeAt,
  pinchApertureFromFrame,
  pinchApertureWindowStats,
} from "./overlayMetricEvidence";
import {
  drawClinicalSkeleton,
  drawChalkJoint,
  drawChalkStick,
  CHALK_PALETTE,
  HAND_FINGER_ORDER,
  SKELETON_PALETTE,
} from "./clinicalSkeleton";
import {
  buildPoseRestHand,
  buildSmoothedTracks,
  hlTipsOffPoseHand,
  interpPair,
  resolveHandDrawSource,
  shouldDrawHlFingers,
} from "./overlayHandTrack";

/** Same background treatment as App.js shell (bg.jpg + blur/dim). */
const APP_BG_URL = "/bg.jpg";
const APP_BG_FILTER = "blur(24px) brightness(0.55) saturate(0.80)";
const APP_BG_SCALE = "scale(1.08)";
const APP_BG_OVERLAY = "rgba(8, 8, 8, 0.18)";

function AppShellBackground({ className = "" }) {
  return (
    <div className={`validation-player-shell-bg pointer-events-none absolute inset-0 overflow-hidden ${className}`} aria-hidden="true">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `url('${APP_BG_URL}')`,
          backgroundSize: "cover",
          backgroundPosition: "center center",
          backgroundRepeat: "no-repeat",
          filter: APP_BG_FILTER,
          transform: APP_BG_SCALE,
        }}
      />
      <div className="absolute inset-0" style={{ background: APP_BG_OVERLAY }} />
    </div>
  );
}

export function computeOverlayMetrics(overlayData) {
  if (!overlayData?.frames?.length) return null;
  const frames = overlayData.frames;
  const fps = overlayData.fps || 60;
  const win = overlayData.movement_window || { start_idx: 0, end_idx: frames.length - 1 };
  const startIdx = Math.max(0, Math.min(frames.length - 1, win.start_idx || 0));
  const endIdx = Math.max(startIdx, Math.min(frames.length - 1, win.end_idx || frames.length - 1));
  const peakFrames = overlayData.peak_frames || [];

  const t0 = frames[startIdx]?.time != null ? frames[startIdx].time : startIdx / fps;
  const t1 = frames[endIdx]?.time != null ? frames[endIdx].time : endIdx / fps;
  const movementTime = Math.max(0, t1 - t0);

  // Peak elbow angular velocity (deg/sec) within the movement window.
  let peakElbowAngVel = 0;
  let peakElbowIdx = startIdx;
  for (let i = startIdx + 1; i <= endIdx; i++) {
    const a1 = frames[i - 1]?.elbow_angle;
    const a2 = frames[i]?.elbow_angle;
    if (a1 == null || a2 == null) continue;
    const dt = (frames[i]?.time != null && frames[i - 1]?.time != null)
      ? Math.max(1e-6, frames[i].time - frames[i - 1].time)
      : 1 / fps;
    const angVel = Math.abs((a2 - a1) / dt);
    if (angVel > peakElbowAngVel) {
      peakElbowAngVel = angVel;
      peakElbowIdx = i;
    }
  }
  const tPeak = frames[peakElbowIdx]?.time != null ? frames[peakElbowIdx].time : peakElbowIdx / fps;
  const timeToPeak = Math.max(0, tPeak - t0);

  // Pause/stop detection based on hand speed ? path pauses only.
  // Terminal low-speed dwell (grasp fixation) is reported separately so a
  // successful grasp does not inflate pause vs an incomplete reach.
  const handSpeeds = frames.map((f) => f.speed || 0);
  const winSpeeds = handSpeeds.slice(startIdx, endIdx + 1);
  const handPeakV = winSpeeds.length ? Math.max(...winSpeeds) : 0;
  const speedThreshold = handPeakV > 0 ? 0.05 * handPeakV : 1.0;
  const minPauseFrames = Math.max(3, Math.round(0.08 * fps));
  const below = winSpeeds.map((s) => (s || 0) < speedThreshold);
  const runs = [];
  for (let i = 0; i < below.length; ) {
    if (!below[i]) { i += 1; continue; }
    let j = i;
    while (j + 1 < below.length && below[j + 1]) j += 1;
    if (j - i + 1 >= minPauseFrames) runs.push([i, j]);
    i = j + 1;
  }
  const terminalCut = Math.floor(below.length * 0.82);
  const isTerminal = ([r0, r1]) => r1 >= below.length - 1 || r0 >= terminalCut;
  let pathRuns = [];
  let dwellRuns = [];
  runs.forEach((run) => {
    if (isTerminal(run)) dwellRuns.push(run);
    else pathRuns.push(run);
  });
  if (runs.length && !pathRuns.length && dwellRuns.length) {
    pathRuns = dwellRuns;
    dwellRuns = [];
  }
  const sumFrames = (rs) => rs.reduce((a, [a0, a1]) => a + (a1 - a0 + 1), 0);
  const pauseTime = sumFrames(pathRuns) / fps;
  const stops = pathRuns.length;
  const graspDwellSec = sumFrames(dwellRuns) / fps;
  const pauseTimeTotal = pauseTime + graspDwellSec;

  let pathLength = 0;
  const startPalm = frames[startIdx]?.palm;
  for (let i = startIdx + 1; i <= endIdx; i++) {
    const prev = frames[i - 1]?.palm;
    const curr = frames[i]?.palm;
    if (prev && curr) pathLength += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
  }
  const endPalm = frames[endIdx]?.palm;
  let straightness = 0;
  if (startPalm && endPalm && pathLength > 0) {
    const displacement = Math.hypot(endPalm[0] - startPalm[0], endPalm[1] - startPalm[1]);
    straightness = Math.min(1, displacement / pathLength);
  }

  let trunkRatio = 0;
  const trunkStart = frames[startIdx]?.trunk;
  const trunkEnd = frames[endIdx]?.trunk;
  if (trunkStart && trunkEnd && startPalm && endPalm) {
    const trunkDisp = Math.abs(trunkEnd[0] - trunkStart[0]);
    const palmDisp = Math.hypot(endPalm[0] - startPalm[0], endPalm[1] - startPalm[1]);
    if (palmDisp > 0) trunkRatio = Math.min(1, trunkDisp / palmDisp);
  }

  // Shoulder elevation = ratio of affected shoulder height above shoulder midpoint.
  let shoulderElevation = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const v = frames[i]?.shoulder_elevation_norm;
    if (v != null && !Number.isNaN(v)) {
      shoulderElevation = Math.max(shoulderElevation, v);
    }
  }

  // Shoulder elevation relative to detected table surface line.
  let shoulderElevationTable = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const v = frames[i]?.shoulder_elevation_table_ratio;
    if (v != null && !Number.isNaN(v)) {
      shoulderElevationTable = Math.max(shoulderElevationTable, v);
    }
  }
  if (!shoulderElevationTable && overlayData?.metrics?.shoulder_elevation_table_ratio != null) {
    shoulderElevationTable = Number(overlayData.metrics.shoulder_elevation_table_ratio);
  }

  // Shoulder elevation relative to vertical projection on the palm/table level (fixed at rest).
  let shoulderElevationPalm = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const v = frames[i]?.shoulder_elevation_palm_ratio;
    if (v != null && !Number.isNaN(v)) {
      shoulderElevationPalm = Math.max(shoulderElevationPalm, v);
    }
  }
  if (!shoulderElevationPalm && overlayData?.metrics?.shoulder_elevation_palm_ratio != null) {
    shoulderElevationPalm = Number(overlayData.metrics.shoulder_elevation_palm_ratio);
  }

  let elbowAngleMean = 0;
  let elbowAngleCount = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const a = frames[i]?.elbow_angle;
    if (a != null && !Number.isNaN(a)) {
      elbowAngleMean += a;
      elbowAngleCount++;
    }
  }
  if (elbowAngleCount > 0) elbowAngleMean /= elbowAngleCount;

  const out = {
    nvp: peakFrames.length,
    straightness,
    pause_time_sec: pauseTime,
    number_of_stops: stops,
    pause_time_sec_total: pauseTimeTotal,
    grasp_dwell_sec: graspDwellSec,
    trunk_ratio: trunkRatio,
    shoulder_elevation_norm: shoulderElevation,
    shoulder_vert_norm: shoulderElevation,
    shoulder_elevation_table_ratio: shoulderElevationTable,
    shoulder_elevation_palm_ratio: shoulderElevationPalm,
    shoulder_elevation_cm:
      overlayData?.metrics?.shoulder_elevation_cm != null
        ? Number(overlayData.metrics.shoulder_elevation_cm)
        : null,
    peak_velocity_cm_s:
      overlayData?.metrics?.peak_velocity_cm_s != null
        ? Number(overlayData.metrics.peak_velocity_cm_s)
        : (overlayData?.peak_velocity_cm_s != null ? Number(overlayData.peak_velocity_cm_s) : null),
    elbow_angle_mean_deg: elbowAngleMean,
    movement_time_sec: movementTime,
    peak_elbow_ang_vel_deg_s: peakElbowAngVel,
    time_to_peak_velocity_sec: timeToPeak,
  };

  if (movementTime > 0) {
    out.relative_time_to_peak_pct = (timeToPeak / movementTime) * 100;
  }

  const backend = overlayData?.metrics;
  if (backend && typeof backend === "object") {
    const passthrough = [
      "validation_adl_phase_id",
      "clinical_task",
      "adl_shoulder_abduction_mean_deg",
      "adl_shoulder_abduction_rom_deg",
      "adl_finger_flex_ext_rom_sw",
      "adl_finger_flex_ext_quality_index",
      "adl_head_forward_flexion_compensation_index",
      "adl_head_flexion_increase_deg",
      "finger_flex_ext_rom_sw",
      "finger_flex_ext_quality_index",
      "head_forward_flexion_compensation_index",
      "head_flexion_increase_deg",
      "shoulder_abduction_mean_deg",
      "shoulder_abduction_rom_deg",
      "movement_quality_index",
    ];
    for (const k of passthrough) {
      if (backend[k] != null && backend[k] !== "") out[k] = backend[k];
    }
  }

  const tremor = resolveTremorMetrics(overlayData);
  if (tremor) {
    Object.assign(out, tremor);
  }

  return out;
}

/** Map video.currentTime to overlay frame index (handles duration drift vs served MP4). */
function getOverlayFrameIndex(frames, fps, playbackTime, videoDuration) {
  return getOverlayFrameState(frames, fps, playbackTime, videoDuration).idx;
}

/** Frame index + blend alpha for smooth landmark sync between overlay samples. */
function getOverlayFrameState(frames, fps, playbackTime, videoDuration) {
  if (!frames?.length) return { idx: 0, alpha: 0 };
  const t0 = frames[0].time ?? 0;
  const tN = frames[frames.length - 1].time ?? t0 + (frames.length - 1) / fps;
  const overlaySpan = tN - t0;
  let targetTime = playbackTime;
  if (videoDuration > 0 && overlaySpan > 1e-6) {
    targetTime = t0 + (playbackTime / videoDuration) * overlaySpan;
  } else {
    targetTime = t0 + playbackTime;
  }
  targetTime = Math.max(t0, Math.min(tN, targetTime));

  if (frames.length === 1) return { idx: 0, alpha: 0 };

  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    const tm = frames[mid].time ?? t0 + mid / fps;
    if (tm <= targetTime) lo = mid;
    else hi = mid;
  }
  const tLo = frames[lo].time ?? t0 + lo / fps;
  const tHi = frames[hi].time ?? t0 + hi / fps;
  const alpha = tHi > tLo + 1e-9 ? Math.max(0, Math.min(1, (targetTime - tLo) / (tHi - tLo))) : 0;
  return { idx: lo, alpha };
}

function overlayCanvasDpr() {
  const raw = window.devicePixelRatio || 1;
  const coarse = window.matchMedia?.("(pointer: coarse)")?.matches || navigator.maxTouchPoints > 0;
  // iPad/touch: cap at 1.0 ? large canvases block the main thread and lag video + overlay.
  return Math.min(raw, coarse ? 1 : 2);
}

function isCoarsePointerDevice() {
  if (typeof window === "undefined") return false;
  return window.matchMedia?.("(pointer: coarse)")?.matches || navigator.maxTouchPoints > 0;
}

/** Fit overlay canvas to the letterboxed video picture (object-fit: contain). */
function syncOverlayCanvas(video, canvas, overlayData, layoutCache, contentWrap, opts = {}) {
  if (!video || !canvas) return null;
  const dpr = overlayCanvasDpr();
  const nativeBuffer = Boolean(opts.nativeBuffer);
  const elW = video.clientWidth || 0;
  const elH = video.clientHeight || 0;
  if (elW < 1 || elH < 1) return null;

  let vw = video.videoWidth || 0;
  let vh = video.videoHeight || 0;
  const ofw = Number(overlayData?.frame_width_px) || 0;
  const ofh = Number(overlayData?.frame_height_px) || 0;
  if (overlayData?.coord_remap === "portrait_to_landscape" && ofw > 0 && ofh > 0) {
    vw = ofw;
    vh = ofh;
  } else if (!vw || !vh) {
    vw = ofw || elW;
    vh = ofh || elH;
  }
  const boxW = contentWrap?.clientWidth || elW;
  const boxH = contentWrap?.clientHeight || elH;
  const cacheKey = `${boxW}|${boxH}|${elW}|${elH}|${vw}|${vh}|${dpr}|${nativeBuffer ? 1 : 0}`;
  if (layoutCache?.key === cacheKey && layoutCache.result) {
    return layoutCache.result;
  }

  const scale = Math.min(elW / vw, elH / vh);
  const displayW = vw * scale;
  const displayH = vh * scale;
  const offsetX = (elW - displayW) / 2;
  const offsetY = (elH - displayH) / 2;

  canvas.style.position = "absolute";
  canvas.style.left = `${offsetX}px`;
  canvas.style.top = `${offsetY}px`;
  canvas.style.width = `${displayW}px`;
  canvas.style.height = `${displayH}px`;

  // Native buffer = full video pixels (Drive bake / no upscale blur).
  // Display buffer = CSS size ? DPR (lighter while watching).
  const pw = Math.max(1, Math.round(nativeBuffer ? vw : displayW * dpr));
  const ph = Math.max(1, Math.round(nativeBuffer ? vh : displayH * dpr));
  if (canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
  }
  const result = { cw: pw, ch: ph };
  if (layoutCache) {
    layoutCache.key = cacheKey;
    layoutCache.result = result;
  }
  return result;
}

function placeGutterChrome(el, style, minSize = 8) {
  if (!el) return;
  const w = style.width ?? 0;
  const h = style.height ?? 0;
  if (w < minSize || h < minSize) {
    el.style.display = "none";
    return;
  }
  el.style.display = "block";
  el.style.position = "absolute";
  el.style.left = `${style.left ?? 0}px`;
  el.style.top = `${style.top ?? 0}px`;
  el.style.width = `${w}px`;
  el.style.height = `${h}px`;
}

/** Full letterbox gutter width for the metrics panel. */
function panelZoneWidth(gutterCss) {
  return Math.max(0, gutterCss);
}

/** App.js Glass / content-panel-glass + comorbidity card tokens. */
const PANEL_GLASS_FILL = "rgba(255,255,255,0.028)";
const PANEL_GLASS_STROKE = "rgba(255,255,255,0.05)";
const PANEL_CARD_FILL = "rgba(255,255,255,0.05)";
const PANEL_CARD_STROKE = "rgba(255,255,255,0.04)";
const PANEL_CARD_INSET = "rgba(255,255,255,0.018)";

/** App.js .glass-float / top bar tokens (canvas approximation; blur from CSS on gutter). */
const APP_GLASS_FILL = "rgba(255,255,255,0.008)";
const APP_GLASS_STROKE = "rgba(255,255,255,0.03)";
const APP_GLASS_INSET = "rgba(255,255,255,0.02)";

function glassRoundPath(ctx, x, y, w, h, radius) {
  const rr = Math.min(radius, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.lineTo(x + w - rr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
  ctx.lineTo(x + w, y + h - rr);
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
  ctx.lineTo(x + rr, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
  ctx.lineTo(x, y + rr);
  ctx.quadraticCurveTo(x, y, x + rr, y);
  ctx.closePath();
}

/** Comorbidity-style inner cards (bg-white/[0.05] border-white/[0.04]). */
function drawPanelCardRect(ctx, x, y, w, h, radius, opts = {}) {
  if (w < 2 || h < 2) return;
  const {
    fill = PANEL_CARD_FILL,
    stroke = PANEL_CARD_STROKE,
    lineW = 1,
  } = opts;
  ctx.save();
  glassRoundPath(ctx, x, y, w, h, radius);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = PANEL_CARD_INSET;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x + radius, y + 0.5);
  ctx.lineTo(x + w - radius, y + 0.5);
  ctx.stroke();
  if (stroke) {
    glassRoundPath(ctx, x, y, w, h, radius);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lineW;
    ctx.stroke();
  }
  ctx.restore();
}

/** Same liquid-glass look as top bar (.glass-float in App.js). */
function drawAppGlassRect(ctx, x, y, w, h, radius, opts = {}) {
  if (w < 2 || h < 2) return;
  const {
    fill = APP_GLASS_FILL,
    stroke = APP_GLASS_STROKE,
    lineW = 1,
    shadow = true,
  } = opts;
  ctx.save();
  if (shadow) {
    ctx.shadowColor = "rgba(0,0,0,0.10)";
    ctx.shadowBlur = 20;
    ctx.shadowOffsetY = 0;
  }
  glassRoundPath(ctx, x, y, w, h, radius);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;

  const topGlow = ctx.createRadialGradient(x + w / 2, y, 0, x + w / 2, y, w * 0.75);
  topGlow.addColorStop(0, "rgba(255,255,255,0.015)");
  topGlow.addColorStop(1, "rgba(255,255,255,0)");
  glassRoundPath(ctx, x, y, w, h, radius);
  ctx.fillStyle = topGlow;
  ctx.fill();

  const bottomGlow = ctx.createRadialGradient(x + w / 2, y + h, 0, x + w / 2, y + h, w * 0.7);
  bottomGlow.addColorStop(0, "rgba(200,230,255,0.015)");
  bottomGlow.addColorStop(1, "rgba(200,230,255,0)");
  glassRoundPath(ctx, x, y, w, h, radius);
  ctx.fillStyle = bottomGlow;
  ctx.fill();

  const sheen = ctx.createLinearGradient(x, y, x, y + h);
  sheen.addColorStop(0, "rgba(255,255,255,0.008)");
  sheen.addColorStop(0.4, "rgba(255,255,255,0)");
  sheen.addColorStop(0.7, "rgba(255,255,255,0)");
  sheen.addColorStop(1, "rgba(255,255,255,0.005)");
  glassRoundPath(ctx, x, y, w, h, radius);
  ctx.fillStyle = sheen;
  ctx.fill();

  ctx.strokeStyle = APP_GLASS_INSET;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x + radius, y + 0.5);
  ctx.lineTo(x + w - radius, y + 0.5);
  ctx.stroke();

  if (stroke) {
    glassRoundPath(ctx, x, y, w, h, radius);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lineW;
    ctx.stroke();
  }
  ctx.restore();
}

function drawPanelChartLine(canvas, profile, endIdx, strokeColor, normalizeMinMax = false) {
  if (!canvas || !profile?.v?.length) return;
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight;
  if (cssW < 2 || cssH < 2) return;
  const pw = Math.round(cssW * dpr);
  const ph = Math.round(cssH * dpr);
  if (canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, pw, ph);
  const plotPadX = 8 * dpr;
  const plotPadTop = 16 * dpr;
  const plotPadBottom = 6 * dpr;
  const plotX0 = plotPadX;
  const plotW = pw - plotPadX * 2;
  const plotY0 = plotPadTop;
  const plotH = ph - plotPadTop - plotPadBottom;
  const vals = profile.v;
  const endI = Math.min(endIdx, vals.length - 1);
  let minV = 0;
  let maxV = 1;
  if (normalizeMinMax) {
    minV = Math.min(...vals);
    maxV = Math.max(1, Math.max(...vals));
  } else {
    maxV = Math.max(1, ...vals);
  }
  const range = maxV - minV || 1;
  ctx.beginPath();
  for (let i = 0; i <= endI; i++) {
    const v = vals[i];
    const x = plotX0 + (i / Math.max(1, vals.length - 1)) * plotW;
    const y = plotY0 + plotH - ((v - minV) / range) * plotH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1.75 * dpr;
  ctx.lineJoin = "round";
  ctx.stroke();
}

/** @deprecated use drawPanelCardRect ? kept for inline fallback */
function drawLightGlassRect(ctx, x, y, w, h, radius, opts = {}) {
  drawPanelCardRect(ctx, x, y, w, h, radius, opts);
}

/** Sparkline for Drive/product bake (no DOM canvas). */
function drawBakeSparkline(ctx, profile, endIdx, x, y, w, h, strokeColor, normalizeMinMax = false) {
  if (!ctx || !profile?.v?.length || w < 8 || h < 8) return;
  const vals = profile.v;
  const endI = Math.min(Math.max(0, endIdx), vals.length - 1);
  let minV = 0;
  let maxV = 1;
  if (normalizeMinMax) {
    minV = Math.min(...vals);
    maxV = Math.max(1, Math.max(...vals));
  } else {
    maxV = Math.max(1, ...vals);
  }
  const range = maxV - minV || 1;
  const padX = 6;
  const padTop = 14;
  const padBottom = 4;
  const plotW = w - padX * 2;
  const plotH = h - padTop - padBottom;
  ctx.beginPath();
  for (let i = 0; i <= endI; i += 1) {
    const px = x + padX + (i / Math.max(1, vals.length - 1)) * plotW;
    const py = y + padTop + plotH - ((vals[i] - minV) / range) * plotH;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1.75;
  ctx.lineJoin = "round";
  ctx.stroke();
}

/**
 * Product metrics gutter burned into Drive bake frames ?
 * glass shell + metric cards + charts (matches ValidationOverlayPlayer UI).
 */
function drawBakeProductPanel(ctx, x, y, w, h, hud) {
  if (!ctx || !hud || w < 48 || h < 48) return;
  const pad = Math.max(10, Math.round(w * 0.045));
  const outerR = Math.max(16, Math.round(w * 0.045));
  drawAppGlassRect(ctx, x, y, w, h, outerR, { shadow: false });

  const formatValue = typeof hud.formatValue === "function"
    ? hud.formatValue
    : (v, digits = 2) => {
      if (v == null || Number.isNaN(v)) return "";
      if (digits === 0) return Math.round(v).toString();
      return Number(v).toFixed(digits);
    };
  const color = hud.color || { text: "#7dd3fc", main: "#38bdf8" };
  const rowDefs = hud.rowDefs || [];
  const live = hud.live || {};
  const overlayData = hud.overlayData;

  const headerH = Math.max(22, Math.round(h * 0.045));
  let cy = y + pad;
  ctx.font = `bold ${Math.max(12, Math.round(w * 0.055))}px sans-serif`;
  ctx.fillStyle = "#fff";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(String(hud.phaseLabel || "Trial"), x + pad, cy + headerH / 2);
  ctx.fillStyle = color.text || "#7dd3fc";
  ctx.textAlign = "right";
  ctx.fillText(`NVP ${hud.nvp ?? 0}`, x + w - pad, cy + headerH / 2);
  ctx.textAlign = "left";
  cy += headerH + Math.round(pad * 0.55);

  const showHand = hud.velocityProfile?.v?.length >= 2;
  const showElbow = Boolean(hud.elbowProfile?.v?.length);
  const showTrunk = Boolean(hud.trunkProfile?.v?.length);
  const chartCount = (showHand ? 1 : 0) + (showElbow ? 1 : 0) + (showTrunk ? 1 : 0);
  const chartH = chartCount > 0 ? Math.max(36, Math.min(52, Math.round(h * 0.07))) : 0;
  const chartsBlock = chartCount > 0 ? chartCount * (chartH + 6) + pad : 0;
  const rowsBottom = y + h - pad - chartsBlock;
  const rowGap = 4;
  const n = Math.max(1, rowDefs.length);
  const avail = Math.max(40, rowsBottom - cy);
  const rowH = Math.min(42, Math.max(22, (avail - rowGap * (n - 1)) / n));
  const cardR = Math.max(8, Math.round(rowH * 0.35));
  const fsLabel = Math.max(9, Math.round(w * 0.042));
  const fsVal = Math.max(10, Math.round(w * 0.048));

  rowDefs.forEach((row) => {
    if (cy + rowH > rowsBottom + 1) return;
    drawPanelCardRect(ctx, x + pad, cy, w - pad * 2, rowH, cardR);
    const valueText = formatPanelRowValue(row, live, overlayData, formatValue);
    ctx.font = `600 ${fsLabel}px sans-serif`;
    ctx.fillStyle = "rgba(255,255,255,0.50)";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(row.label, x + pad + 10, cy + rowH / 2);
    ctx.font = `bold ${fsVal}px sans-serif`;
    ctx.fillStyle = row.accent ? (color.text || "#7dd3fc") : "rgba(255,255,255,0.94)";
    ctx.textAlign = "right";
    ctx.fillText(valueText, x + w - pad - 10, cy + rowH / 2);
    ctx.textAlign = "left";
    cy += rowH + rowGap;
  });

  cy = y + h - pad - chartsBlock + 2;
  const chartW = w - pad * 2;
  const paintChart = (label, profile, stroke, normalize) => {
    drawPanelCardRect(ctx, x + pad, cy, chartW, chartH, cardR);
    ctx.font = `600 ${Math.max(9, Math.round(fsLabel * 0.9))}px sans-serif`;
    ctx.fillStyle = "rgba(255,255,255,0.50)";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(label, x + pad + 8, cy + 5);
    drawBakeSparkline(ctx, profile, hud.idx ?? 0, x + pad, cy, chartW, chartH, stroke, normalize);
    cy += chartH + 6;
  };
  if (showHand) paintChart("Hand speed", hud.velocityProfile, color.main || "#38bdf8", false);
  if (showElbow) paintChart("Elbow angle", hud.elbowProfile, "#7dd3fc", true);
  if (showTrunk) paintChart("Trunk", hud.trunkProfile, "#facc15", true);
}

function drawThinDivider(ctx, x0, x1, y, alpha = 0.16) {
  ctx.save();
  ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x0, y);
  ctx.lineTo(x1, y);
  ctx.stroke();
  ctx.restore();
}

/** Letterbox gutters are transparent ? app bg.jpg shows through (see index.css). */
function drawAmbientFromVideo() {
  return null;
}

/** Position letterbox gutters (does not touch overlay mapping). */
function syncLetterboxGutters(video, stageEl, gutters, contentWrap, absoluteVideoBox = false) {
  if (!video || !stageEl) return { externalPanel: false, rightGutter: 0 };
  const stageW = stageEl.clientWidth;
  const stageH = stageEl.clientHeight;
  if (stageW < 2 || stageH < 2) return { externalPanel: false, rightGutter: 0 };

  const vw = video.videoWidth || 0;
  const vh = video.videoHeight || 0;
  if (!vw || !vh) return { externalPanel: false, rightGutter: 0 };

  const scale = Math.min(stageW / vw, stageH / vh);
  const displayW = vw * scale;
  const displayH = vh * scale;
  const vidLeft = (stageW - displayW) / 2;
  const vidTop = (stageH - displayH) / 2;

  if (contentWrap) {
    if (absoluteVideoBox) {
      contentWrap.style.position = "absolute";
      contentWrap.style.left = `${vidLeft}px`;
      contentWrap.style.top = `${vidTop}px`;
      contentWrap.style.width = `${displayW}px`;
      contentWrap.style.height = `${displayH}px`;
      contentWrap.style.flexShrink = "0";
      contentWrap.style.zIndex = "8";
    } else {
      contentWrap.style.position = "";
      contentWrap.style.left = "";
      contentWrap.style.top = "";
      contentWrap.style.width = `${displayW}px`;
      contentWrap.style.height = `${displayH}px`;
      contentWrap.style.flexShrink = "0";
      contentWrap.style.zIndex = "";
    }
  }
  video.style.width = "100%";
  video.style.height = "100%";

  const leftG = Math.max(0, vidLeft);
  const topG = Math.max(0, vidTop);
  const rightG = Math.max(0, stageW - vidLeft - displayW);
  const bottomG = Math.max(0, stageH - vidTop - displayH);

  placeGutterChrome(gutters.left, { left: 0, top: 0, width: leftG, height: stageH });
  placeGutterChrome(gutters.right, { left: stageW - rightG, top: 0, width: rightG, height: stageH });
  placeGutterChrome(gutters.top, { left: leftG, top: 0, width: stageW - leftG - rightG, height: topG });
  placeGutterChrome(gutters.bottom, { left: leftG, top: stageH - bottomG, width: stageW - leftG - rightG, height: bottomG });

  const panelW = panelZoneWidth(rightG);
  const externalPanel = panelW >= 72;

  return {
    externalPanel,
    rightGutter: rightG,
    panelW,
    panelH: stageH,
    stageW,
    stageH,
    leftG,
    topG,
    rightG,
    bottomG,
  };
}

function pickOverlayMetric(overlayData, keys) {
  const m = overlayData?.metrics || {};
  for (const k of keys) {
    const v = m[k];
    if (v != null && v !== "" && !Number.isNaN(Number(v))) return Number(v);
  }
  return null;
}

function isLeClinicalTask(clinicalTask, overlayData) {
  const m = overlayData?.metrics || {};
  const task = String(clinicalTask || m.clinical_task || overlayData?.clinical_task || "").toLowerCase();
  return (
    task === "sts_stand"
    || task === "bodyweight_squat"
    || task === "overground_gait"
    || task === "quiet_stance_balance"
    || m.le_analysis === true
    || m.gait_speed_m_s != null
    || m.ankle_df_peak_L_deg != null
    || m.sts_time_sec != null
    || m.com_sway_path_norm != null
  );
}

const DEG = "\u00B0";
const PANEL_EMPTY = "\u2014";

/** Full LE / gait / core validation panel ? all product variables. */
const LE_VALIDATION_PANEL_ROWS = [
  { id: "mov_time", label: "Movement time", kind: "metric", metricKeys: ["movement_time_sec", "sts_time_sec"], suffix: " s", decimals: 2 },
  { id: "mov_quality", label: "Quality index", kind: "metric", metricKeys: ["movement_quality_index"] },
  { id: "sparc_com", label: "SPARC (COM)", kind: "metric", metricKeys: ["sparc_com"], decimals: 2 },
  { id: "lr_sym", label: "L/R symmetry", kind: "metric", metricKeys: ["lr_symmetry_index"], decimals: 2 },
  { id: "gait_speed", label: "Gait speed", kind: "metric", metricKeys: ["gait_speed_m_s"], suffix: " m/s", decimals: 2 },
  { id: "cadence", label: "Cadence", kind: "metric", metricKeys: ["cadence_spm"], suffix: " /min", decimals: 0 },
  { id: "speed_pct", label: "Speed % of norm", kind: "metric", metricKeys: ["pct_of_norm_gait_speed_m_s"], suffix: "%", decimals: 0 },
  { id: "cadence_pct", label: "Cadence % of norm", kind: "metric", metricKeys: ["pct_of_norm_cadence_spm"], suffix: "%", decimals: 0 },
  { id: "df_l", label: "Ankle DF L", kind: "metric", metricKeys: ["ankle_df_peak_L_deg"], suffix: DEG, decimals: 1 },
  { id: "df_r", label: "Ankle DF R", kind: "metric", metricKeys: ["ankle_df_peak_R_deg"], suffix: DEG, decimals: 1 },
  { id: "pf_l", label: "Ankle PF L", kind: "metric", metricKeys: ["ankle_pf_peak_L_deg"], suffix: DEG, decimals: 1 },
  { id: "pf_r", label: "Ankle PF R", kind: "metric", metricKeys: ["ankle_pf_peak_R_deg"], suffix: DEG, decimals: 1 },
  { id: "df_pct", label: "DF L % of norm", kind: "metric", metricKeys: ["pct_of_norm_ankle_df_peak_L_deg"], suffix: "%", decimals: 0 },
  { id: "pf_pct", label: "PF L % of norm", kind: "metric", metricKeys: ["pct_of_norm_ankle_pf_peak_L_deg"], suffix: "%", decimals: 0 },
  { id: "ankle_rom_l", label: "Ankle ROM L", kind: "metric", metricKeys: ["ankle_sagittal_rom_L_deg"], suffix: DEG, decimals: 1 },
  { id: "ankle_rom_r", label: "Ankle ROM R", kind: "metric", metricKeys: ["ankle_sagittal_rom_R_deg"], suffix: DEG, decimals: 1 },
  { id: "fpa_l", label: "Foot progression L", kind: "metric", metricKeys: ["foot_progression_angle_L_deg"], suffix: DEG, decimals: 1 },
  { id: "fpa_r", label: "Foot progression R", kind: "metric", metricKeys: ["foot_progression_angle_R_deg"], suffix: DEG, decimals: 1 },
  { id: "hip_rot_l", label: "Hip rot ROM L", kind: "metric", metricKeys: ["hip_rotation_rom_L_deg"], suffix: DEG, decimals: 1 },
  { id: "hip_rot_r", label: "Hip rot ROM R", kind: "metric", metricKeys: ["hip_rotation_rom_R_deg"], suffix: DEG, decimals: 1 },
  { id: "knee_sw_l", label: "Swing knee flex L", kind: "metric", metricKeys: ["knee_flex_peak_swing_L_deg"], suffix: DEG, decimals: 1 },
  { id: "knee_sw_r", label: "Swing knee flex R", kind: "metric", metricKeys: ["knee_flex_peak_swing_R_deg"], suffix: DEG, decimals: 1 },
  { id: "hip_rom_l", label: "Hip ROM L", kind: "metric", metricKeys: ["hip_rom_L_deg"], suffix: DEG, decimals: 1 },
  { id: "hip_rom_r", label: "Hip ROM R", kind: "metric", metricKeys: ["hip_rom_R_deg"], suffix: DEG, decimals: 1 },
  { id: "knee_rom_l", label: "Knee ROM L", kind: "metric", metricKeys: ["knee_rom_L_deg"], suffix: DEG, decimals: 1 },
  { id: "knee_rom_r", label: "Knee ROM R", kind: "metric", metricKeys: ["knee_rom_R_deg"], suffix: DEG, decimals: 1 },
  { id: "pelvis_rot", label: "Pelvis rotation ROM", kind: "metric", metricKeys: ["pelvis_rotation_rom_deg"], suffix: DEG, decimals: 1 },
  { id: "trunk_lean", label: "Trunk lean max", kind: "metric", metricKeys: ["trunk_lean_max_deg"], suffix: DEG, decimals: 1 },
  { id: "trunk_flex", label: "Trunk flexion ROM", kind: "metric", metricKeys: ["trunk_flexion_rom_deg"], suffix: DEG, decimals: 1 },
  { id: "trunk_comp", label: "Trunk compensation", kind: "metric", metricKeys: ["trunk_compensation_index"], decimals: 2 },
  { id: "step_l", label: "Step time L", kind: "metric", metricKeys: ["step_time_L_sec"], suffix: " s", decimals: 2 },
  { id: "step_r", label: "Step time R", kind: "metric", metricKeys: ["step_time_R_sec"], suffix: " s", decimals: 2 },
  { id: "step_sym", label: "Step timing symmetry", kind: "metric", metricKeys: ["step_length_symmetry"], decimals: 2 },
  { id: "foot_drop", label: "Foot-drop index", kind: "metric", metricKeys: ["foot_drop_index"], decimals: 2 },
  { id: "foot_slap", label: "Foot-slap index", kind: "metric", metricKeys: ["foot_slap_index"], decimals: 2 },
  { id: "push_off", label: "Push-off deficit", kind: "metric", metricKeys: ["push_off_deficit_index"], decimals: 2 },
  { id: "stiff_knee", label: "Stiff-knee index", kind: "metric", metricKeys: ["stiff_knee_index"], decimals: 2 },
  { id: "hip_hike", label: "Hip-hike index", kind: "metric", metricKeys: ["hip_hike_index"], decimals: 2 },
  { id: "circ", label: "Circumduction index", kind: "metric", metricKeys: ["circumduction_index"], decimals: 2 },
  { id: "vault", label: "Vaulting index", kind: "metric", metricKeys: ["vaulting_index"], decimals: 2 },
  { id: "sts", label: "STS time", kind: "metric", metricKeys: ["sts_time_sec"], suffix: " s", decimals: 2 },
  { id: "com_rise", label: "COM rise (HW)", kind: "metric", metricKeys: ["com_rise_norm"], decimals: 2 },
  { id: "wshift", label: "Weight-shift asym.", kind: "metric", metricKeys: ["weight_shift_asymmetry"], decimals: 2 },
  { id: "squat_depth", label: "Squat depth (HW)", kind: "metric", metricKeys: ["squat_depth_norm"], decimals: 2 },
  { id: "min_knee", label: "Min knee (squat)", kind: "metric", metricKeys: ["min_knee_angle_deg"], suffix: DEG, decimals: 1 },
  { id: "sway_path", label: "COM sway path", kind: "metric", metricKeys: ["com_sway_path_norm"], decimals: 2 },
  { id: "sway_area", label: "COM sway area", kind: "metric", metricKeys: ["com_sway_area_norm"], decimals: 2 },
  { id: "sway_vel", label: "Sway velocity", kind: "metric", metricKeys: ["sway_velocity_mean"], decimals: 1 },
  { id: "load_sym", label: "Loading symmetry", kind: "metric", metricKeys: ["lr_loading_symmetry"], decimals: 2 },
];

function getValidationPanelRowDefs(overlayData, clinicalTask) {
  if (isLeClinicalTask(clinicalTask, overlayData)) {
    return LE_VALIDATION_PANEL_ROWS;
  }
  // UE study / kinematics table variables (live + metrics) ? full panel, not 2-row stub.
  return UE_VALIDATION_PANEL_ROWS;
}

/** Upper-extremity validation panel ? matches kinematics table core + validation extras. */
const UE_VALIDATION_PANEL_ROWS = [
  { id: "mov_time", label: "Movement time", kind: "metric", metricKeys: ["movement_time_sec"], suffix: " s", decimals: 2 },
  { id: "mov_quality", label: "Movement quality", kind: "metric", metricKeys: ["movement_quality_index"], accent: true },
  { id: "straightness", label: "Straightness", kind: "live", key: "straightness", decimals: 2, metricKeys: ["straightness"] },
  { id: "peak_vel", label: "Peak velocity", kind: "peakVelCm", accent: true },
  { id: "pause", label: "Pause / stops", kind: "pause" },
  { id: "trunk", label: "Trunk ratio", kind: "live", key: "trunkRatio", decimals: 2, metricKeys: ["trunk_ratio"] },
  { id: "sh_elev", label: "Shoulder elevation", kind: "shoulderElev" },
  { id: "elbow_mean", label: "Elbow angle mean", kind: "metric", metricKeys: ["elbow_angle_mean_deg", "elbow_angle_mean"], suffix: DEG, decimals: 1 },
  { id: "tremor", label: "Tremor 8-12 Hz", kind: "tremor", tremorKey: "tremor_8_12hz_power" },
  { id: "tremor_hz", label: "Tremor peak freq", kind: "tremorFreq", tremorKey: "tremor_peak_freq_hz" },
  { id: "kin_abd", label: "Shoulder abduction", kind: "live", key: "shoulderAbduction", suffix: DEG, decimals: 0 },
  { id: "kin_finger", label: "Finger quality", kind: "live", key: "fingerQuality", decimals: 0 },
];

function computeLiveFingerQuality(frames, startIdx, idx) {
  if (!frames?.length || idx < startIdx) return null;
  const vals = [];
  for (let i = startIdx; i <= idx; i += 1) {
    const v = frames[i]?.finger_open_sw;
    if (typeof v === "number" && v > 0 && !Number.isNaN(v)) vals.push(v);
  }
  if (!vals.length) return null;
  const peak = Math.max(...vals);
  const rom = vals.length >= 2 ? Math.max(...vals) - Math.min(...vals) : 0;
  let q = 25 * Math.min(1, peak * 4);
  if (rom > 0) q += 45 * Math.min(1, rom * 6);
  if (vals.length >= 3) {
    const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
    const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length);
    if (mu > 1e-6) q += 30 * (1 - Math.min(1, sd / mu));
  }
  return Math.min(100, Math.round(q));
}

const LIVE_PANEL_FALLBACK_KEYS = {
  straightness: ["straightness"],
  trunkRatio: ["trunk_ratio"],
  movementTime: ["movement_time_sec"],
  shoulderAbduction: ["shoulder_abduction_deg"],
  fingerQuality: ["finger_quality_index", "adl_finger_quality_index", "finger_quality"],
};

function formatPanelRowValue(row, live, overlayData, formatValue) {
  if (row.kind === "live") {
    let v = live[row.key];
    if (v == null || Number.isNaN(v) || (v <= 0 && row.id !== "kin_abd" && row.id !== "kin_finger")) {
      const fb = row.metricKeys || LIVE_PANEL_FALLBACK_KEYS[row.key];
      if (fb) {
        const picked = pickOverlayMetric(overlayData, Array.isArray(fb) ? fb : [fb]);
        if (picked != null) v = picked;
      }
    }
    if (v == null || Number.isNaN(v)) return PANEL_EMPTY;
    if ((row.id === "kin_abd" || row.id === "kin_finger") && v <= 0) return PANEL_EMPTY;
    return `${formatValue(v, row.decimals ?? 2)}${row.suffix || ""}`;
  }
  if (row.kind === "peakVelCm") {
    const cm = pickOverlayMetric(overlayData, ["peak_velocity_cm_s"]);
    if (cm != null && Number(cm) > 0) return `${formatValue(Number(cm), 1)} cm/s`;
    const v = live.peakElbowAngVel;
    if (v == null || Number.isNaN(v) || v <= 0) return PANEL_EMPTY;
    return `${formatValue(v, 0)} ${DEG}/s`;
  }
  if (row.kind === "pause") {
    const pauseTime = live.pauseTime ?? 0;
    const stops = live.stops ?? 0;
    const fbPause = pickOverlayMetric(overlayData, ["pause_time_sec"]);
    const fbStops = pickOverlayMetric(overlayData, ["number_of_stops"]);
    const p = pauseTime > 0 ? pauseTime : (fbPause ?? 0);
    const s = stops > 0 ? stops : (fbStops ?? 0);
    if (p <= 0 && s <= 0) return PANEL_EMPTY;
    return `${formatValue(p, 2)} s / ${s}`;
  }
  if (row.kind === "shoulderElev") {
    const cm = pickOverlayMetric(overlayData, ["shoulder_elevation_cm"]);
    if (cm != null && Number(cm) > 0) return `${formatValue(Number(cm), 1)} cm`;
    const v = live.shoulderElevationPalm || live.shoulderElevationTable || live.shoulderElevation;
    if (v > 0) return formatValue(v, 3);
    return PANEL_EMPTY;
  }
  if (row.kind === "tremor") {
    const v = live[row.tremorKey] ?? pickOverlayMetric(overlayData, [row.tremorKey]);
    return formatTremorPower(v) || PANEL_EMPTY;
  }
  if (row.kind === "tremorIndex") {
    const v = live[row.tremorKey];
    if (v == null || Number.isNaN(v)) return PANEL_EMPTY;
    return Math.round(Number(v)).toString();
  }
  if (row.kind === "tremorFreq") {
    const v = live[row.tremorKey] ?? pickOverlayMetric(overlayData, [row.tremorKey]);
    if (v == null || Number.isNaN(Number(v))) return PANEL_EMPTY;
    return `${Number(v).toFixed(1)} Hz`;
  }
  if (row.kind === "metric" && row.metricKeys) {
    const v = pickOverlayMetric(overlayData, row.metricKeys);
    if (v == null) return PANEL_EMPTY;
    const decimals = row.decimals != null ? row.decimals : 2;
    const formatted = formatValue(v, decimals);
    return row.suffix ? `${formatted}${row.suffix}` : formatted;
  }
  return PANEL_EMPTY;
}

export function ValidationOverlayPlayer({
  videoUrl,
  overlayData,
  phaseLabel,
  clinicalTask = null,
  autoPlay = false,
  autoRender = false,
  serverExportFilename = null,
  onRequestServerExport,
  onEnded,
  onDownloadReady,
  onError,
  onSourceMismatch,
}) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const panelDomRef = useRef(null);
  const panelPhaseRef = useRef(null);
  const panelNvpRef = useRef(null);
  const panelMetricValueRefs = useRef([]);
  const chartHandRef = useRef(null);
  const chartElbowRef = useRef(null);
  const chartTrunkRef = useRef(null);
  const chartHandWrapRef = useRef(null);
  const chartElbowWrapRef = useRef(null);
  const chartTrunkWrapRef = useRef(null);
  const stageRef = useRef(null);
  const contentWrapRef = useRef(null);
  const ambientCanvasRef = useRef(null);
  const gutterLeftRef = useRef(null);
  const gutterRightRef = useRef(null);
  const gutterTopRef = useRef(null);
  const gutterBottomRef = useRef(null);
  const containerRef = useRef(null);
  const recCanvasRef = useRef(null);
  const bakeOverlayCanvasRef = useRef(null);
  const bakeOverlayPassRef = useRef(false);
  const recordingRef = useRef(false);
  const bakeHudRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [displayTime, setDisplayTime] = useState(0);
  const [displayDuration, setDisplayDuration] = useState(0);
  const [recording, setRecording] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadBusy, setDownloadBusy] = useState(false);
  /** clinical = bone sticks; chalk = soft chalk limb ribbons (default) */
  const [overlayStyle, setOverlayStyle] = useState("chalk");
  const [renderProgress, setRenderProgress] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [videoAspect, setVideoAspect] = useState(null);
  /** Loaded video is not the clip the overlay was computed from (e.g. a baked composite). */
  const [sourceMismatch, setSourceMismatch] = useState(false);
  const sourceMismatchRef = useRef(false);
  const mismatchReportedRef = useRef(null);
  useEffect(() => {
    sourceMismatchRef.current = false;
    setSourceMismatch(false);
  }, [videoUrl]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isTouchUi, setIsTouchUi] = useState(false);
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);
  const rafRef = useRef(null);
  const vfcIdRef = useRef(null);
  const videoTimeRef = useRef(0);
  const autoRenderStartedRef = useRef(false);
  const pendingDownloadRef = useRef(false);
  const savedTimeRef = useRef(0);
  const wasPlayingRef = useRef(false);
  const canvasLayoutCacheRef = useRef({ key: "", result: null });
  const gutterLayoutCacheRef = useRef({ key: "", result: null });
  const lastPaintMediaTimeRef = useRef(-1);
  const lastPanelUpdateIdxRef = useRef(-1);
  const liveMetricsCacheRef = useRef(null);
  const tremorLiveCacheRef = useRef({ idx: -1, data: null });
  const progressRafRef = useRef(0);
  const paintPendingRef = useRef(false);
  /** Keep last good finger dots briefly so they don't vanish on 1–2 missing frames. */
  const fingerStickyRef = useRef({});
  /** Light same-source EMA only. Cleared on cup↔hand model switch. */
  const fingerSmoothRef = useRef({});
  /** Hysteresis for pose-rest vs HL fingers (must not flicker at movement onset). */
  const handSourceRef = useRef({ src: "pose", offStreak: 0, onStreak: 0 });

  const phaseColor = useMemo(() => {
    const p = (phaseLabel || "").toLowerCase();
    if (p.includes("post")) return { main: "#10b981", glow: "rgba(16,185,129,0.45)", text: "#6ee7b7" };
    if (p.includes("pre")) return { main: "#0ea5e9", glow: "rgba(14,165,233,0.45)", text: "#7dd3fc" };
    return { main: "#f59e0b", glow: "rgba(245,158,11,0.45)", text: "#fcd34d" };
  }, [phaseLabel]);

  const panelRowDefs = useMemo(() => getValidationPanelRowDefs(overlayData, clinicalTask), [overlayData, clinicalTask]);

  const frames = overlayData?.frames || [];
  const fps = overlayData?.fps || 60;
  const smoothTracks = useMemo(
    () => buildSmoothedTracks(overlayData?.frames, overlayData?.fps || 60),
    [overlayData?.frames, overlayData?.fps],
  );
  const metrics = overlayData?.metrics || {};
  const win = overlayData?.movement_window || { start_idx: 0, end_idx: frames.length - 1 };
  const startPalm = overlayData?.start_palm;
  const endPalm = overlayData?.end_palm;
  const velocityProfile = overlayData?.velocity_profile;
  const peakFrames = overlayData?.peak_frames || [];

  const getElbowAngVel = useCallback((idx) => {
    if (idx <= 0 || idx >= frames.length) return 0;
    const a1 = frames[idx - 1]?.elbow_angle;
    const a2 = frames[idx]?.elbow_angle;
    if (a1 == null || a2 == null) return 0;
    const dt = (frames[idx]?.time != null && frames[idx - 1]?.time != null)
      ? Math.max(1e-6, frames[idx].time - frames[idx - 1].time)
      : 1 / fps;
    return Math.abs((a2 - a1) / dt);
  }, [frames, fps]);

  const peakElbowAngVel = useMemo(() => {
    let maxV = 0;
    for (let i = 1; i < frames.length; i++) {
      const v = getElbowAngVel(i);
      if (v > maxV) maxV = v;
    }
    return maxV;
  }, [frames, getElbowAngVel]);
  const peakV = peakElbowAngVel || 1;
  const handPeakV = useMemo(() => {
    const speeds = frames.map((f) => f.speed || 0);
    return speeds.length ? Math.max(...speeds) : 1;
  }, [frames]);

  const getFrameIndex = useCallback((time) => {
    const video = videoRef.current;
    const duration = video?.duration || overlayData?.duration_sec || 0;
    return getOverlayFrameState(frames, fps, time, duration).idx;
  }, [frames, fps, overlayData?.duration_sec]);

  const getFrameState = useCallback((time) => {
    const video = videoRef.current;
    const duration = video?.duration || overlayData?.duration_sec || 0;
    return getOverlayFrameState(frames, fps, time, duration);
  }, [frames, fps, overlayData?.duration_sec]);

  const formatValue = (v, digits = 2) => {
    if (v == null || Number.isNaN(v)) return "";
    if (digits === 0) return Math.round(v).toString();
    return Number(v).toFixed(digits);
  };

  /**
   * Overlay coords are normalized to the analyzed clip. A baked composite (burned-in
   * skeleton + side panel) has a different frame shape and length, so drawing on it puts
   * chalk across the table. Detect that and stop drawing instead of showing wrong lines.
   */
  const checkOverlaySource = useCallback((vw, vh, vDuration) => {
    const overlayW = Number(overlayData?.frame_width_px) || 0;
    const overlayH = Number(overlayData?.frame_height_px) || 0;
    const overlayDur = Number(overlayData?.duration_sec)
      || (frames.length > 1 && fps > 0 ? frames.length / fps : 0);
    const remapped = Boolean(overlayData?.coord_remap);

    let shapeBad = false;
    if (!remapped && vw > 0 && vh > 0 && overlayW > 0 && overlayH > 0) {
      const videoAr = vw / vh;
      const overlayAr = overlayW / overlayH;
      const near = (a, b) => Math.abs(a / b - 1) <= 0.12;
      // A rotated original reports swapped dimensions; that is still the same clip.
      shapeBad = !near(videoAr, overlayAr) && !near(videoAr, 1 / overlayAr);
    }
    const durBad = overlayDur > 0.5
      && Number.isFinite(vDuration)
      && vDuration > 0.2
      && overlayDur - vDuration > overlayDur * 0.3;

    const bad = shapeBad || durBad;
    sourceMismatchRef.current = bad;
    setSourceMismatch(bad);
    if (!bad) {
      mismatchReportedRef.current = null;
      return;
    }
    if (mismatchReportedRef.current === videoUrl) return;
    mismatchReportedRef.current = videoUrl;
    onSourceMismatch?.({
      videoWidth: vw,
      videoHeight: vh,
      videoDuration: Number.isFinite(vDuration) ? vDuration : null,
      overlayWidth: overlayW,
      overlayHeight: overlayH,
      overlayDuration: overlayDur,
      reason: shapeBad ? "frame_shape" : "duration",
    });
  }, [overlayData, frames.length, fps, videoUrl, onSourceMismatch]);

  const drawOverlay = useCallback(() => {
    const bakePass = bakeOverlayPassRef.current;
    const canvas = bakePass ? bakeOverlayCanvasRef.current : canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    if (sourceMismatchRef.current) {
      const ctx0 = canvas.getContext("2d");
      ctx0?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    const stageEl = bakePass ? null : stageRef.current;
    const contentEl = bakePass ? null : contentWrapRef.current;
    let gutterLayout = gutterLayoutCacheRef.current.result || { externalPanel: false };
    if (stageEl) {
      const sw = stageEl.clientWidth;
      const sh = stageEl.clientHeight;
      const vw = video.videoWidth || 0;
      const vh = video.videoHeight || 0;
      const gKey = `${sw}|${sh}|${vw}|${vh}|${isExpanded ? 1 : 0}`;
      if (gutterLayoutCacheRef.current.key !== gKey) {
        gutterLayout = syncLetterboxGutters(video, stageEl, {
          left: gutterLeftRef.current,
          right: gutterRightRef.current,
          top: gutterTopRef.current,
          bottom: gutterBottomRef.current,
        }, contentEl, isExpanded);
        gutterLayoutCacheRef.current = { key: gKey, result: gutterLayout };
        canvasLayoutCacheRef.current = { key: "", result: null };
      }
    }

    if (!video.videoWidth || video.readyState < 1) return;
    let cw;
    let ch;
    if (bakePass) {
      const vw = video.videoWidth || 640;
      const vh = video.videoHeight || 480;
      if (canvas.width !== vw || canvas.height !== vh) {
        canvas.width = vw;
        canvas.height = vh;
      }
      cw = vw;
      ch = vh;
      gutterLayout = { externalPanel: false };
    } else {
      const synced = syncOverlayCanvas(
        video,
        canvas,
        overlayData,
        canvasLayoutCacheRef.current,
        contentEl,
        { nativeBuffer: false },
      );
      if (!synced) return;
      cw = synced.cw;
      ch = synced.ch;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, cw, ch);

    if (stageEl && ambientCanvasRef.current) {
      drawAmbientFromVideo(video, stageEl, ambientCanvasRef.current, gutterLayout, {
        left: gutterLeftRef.current,
        top: gutterTopRef.current,
        bottom: gutterBottomRef.current,
      });
    }
    // Never hide the live side panel during Drive bake ? panel is composited separately.
    const useExternalPanel = !bakePass && Boolean(gutterLayout.externalPanel);
    const panelCtx = ctx;
    if (panelDomRef.current) {
      panelDomRef.current.classList.toggle("hidden", !useExternalPanel);
    }

    if (!frames.length) return;

    const touchPerf = isCoarsePointerDevice();
    const shadowOff = touchPerf ? 4 : undefined;
    // Live drawing must match pre-bake iPad behavior. Bake composites panel separately.
    const baking = Boolean(recordingRef.current);
    const drawRich = !touchPerf;
    const playbackTime = video.currentTime ?? videoTimeRef.current ?? 0;
    const { idx, alpha } = getFrameState(playbackTime);
    // Keep metrics panel fresh from the first frame (not only at movement end).
    const updatePanelMetrics = baking || !touchPerf || video.paused || idx % 3 === 0;
    const updatePanelCharts = baking || !touchPerf || video.paused;
    const f = frames[idx];
    const fNext = frames[Math.min(idx + 1, frames.length - 1)];
    if (!f) return;

    const color = phaseColor;

    const idxNext = Math.min(idx + 1, frames.length - 1);
    const trackPair = (key) => {
      const p = smoothTracks?.at(key, idx) || null;
      if (!p) return null;
      const pn = alpha > 0 ? smoothTracks.at(key, idxNext) : null;
      if (!pn || alpha <= 0) return p;
      return [p[0] + (pn[0] - p[0]) * alpha, p[1] + (pn[1] - p[1]) * alpha];
    };
    const ptCache = new Map();

    function pt(name) {
      if (ptCache.has(name)) return ptCache.get(name);
      const sm = trackPair(name);
      const raw = interpPair(f[name], fNext?.[name], alpha);
      const p = sm || raw;
      let out = null;
      if (p) {
        const isHandLm = /^(index|thumb|pinky|middle|ring|hl_wrist)$/.test(name);
        const edge = p[0] <= 0.0002 || p[0] >= 0.9998 || p[1] <= 0.0002 || p[1] >= 0.9998;
        if (!isHandLm || !edge) out = [p[0] * cw, p[1] * ch];
      }
      ptCache.set(name, out);
      return out;
    }

    function toCanvas(p) {
      if (!p || p[0] == null || p[1] == null) return null;
      return [p[0] * cw, p[1] * ch];
    }

    function line(a, b, opts = {}) {
      if (!a || !b) return;
      const { color = "rgba(255,255,255,0.5)", width = 2, dash = [] } = opts;
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.setLineDash(dash);
      ctx.lineCap = "round";
      ctx.stroke();
      ctx.setLineDash([]);
    }

    function dot(p, opts = {}) {
      if (!p) return;
      const { fill = "#fff", stroke = "rgba(0,0,0,0.5)", r = 4 } = opts;
      ctx.beginPath();
      ctx.arc(p[0], p[1], r, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    function pill(text, p, opts = {}) {
      if (!p) return;
      const {
        offsetX = 10,
        offsetY = -10,
        bg = "rgba(14,17,32,0.72)",
        border = "rgba(255,255,255,0.18)",
        color = "#fff",
        size = "10px",
        padding = 4,
      } = opts;
      ctx.font = `bold ${size} sans-serif`;
      const tm = ctx.measureText(text);
      const tw = tm.width;
      const th = 12;
      let tx = p[0] + offsetX;
      let ty = p[1] + offsetY;
      tx = Math.max(4, Math.min(cw - tw - padding * 2 - 4, tx));
      ty = Math.max(th + padding, Math.min(ch - 4, ty));
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.35)";
      ctx.shadowBlur = 6;
      ctx.fillStyle = bg;
      ctx.strokeStyle = border;
      ctx.lineWidth = 1;
      const r = 6;
      const x = tx - padding, y = ty - th - padding, w = tw + padding * 2, h = th + padding * 2;
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = color;
      ctx.fillText(text, tx, ty);
    }

    function pillWithArrow(text, p, opts = {}) {
      if (!p) return;
      const {
        offsetX = 10,
        offsetY = -10,
        bg = "rgba(14,17,32,0.78)",
        border = "rgba(255,255,255,0.22)",
        color = "#fff",
        size = `${Math.round(10 * window.devicePixelRatio)}px`,
        padding = 5,
      } = opts;
      ctx.font = `bold ${size} sans-serif`;
      const tm = ctx.measureText(text);
      const tw = tm.width;
      const th = Math.round(11 * window.devicePixelRatio);
      let lx = p[0] + offsetX;
      let ly = p[1] + offsetY;
      const w = tw + padding * 2;
      const h = th + padding * 2;
      lx = Math.max(4, Math.min(cw - w - 4, lx));
      ly = Math.max(h + 4, Math.min(ch - 4, ly));
      const cx = lx + w / 2;
      const cy = ly - h / 2;
      ctx.save();
      ctx.strokeStyle = border;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(p[0], p[1]);
      ctx.lineTo(cx, cy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.4)";
      ctx.shadowBlur = 8;
      ctx.fillStyle = bg;
      ctx.strokeStyle = border;
      ctx.lineWidth = 1;
      const rr = 6;
      const x = lx, y = ly - h, ww = w, hh = h;
      ctx.beginPath();
      ctx.moveTo(x + rr, y);
      ctx.lineTo(x + ww - rr, y);
      ctx.quadraticCurveTo(x + ww, y, x + ww, y + rr);
      ctx.lineTo(x + ww, y + hh - rr);
      ctx.quadraticCurveTo(x + ww, y + hh, x + ww - rr, y + hh);
      ctx.lineTo(x + rr, y + hh);
      ctx.quadraticCurveTo(x, y + hh, x, y + hh - rr);
      ctx.lineTo(x, y + rr);
      ctx.quadraticCurveTo(x, y, x + rr, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = color;
      ctx.fillText(text, x + padding, y + h - padding - 2);
    }

    const speed = getElbowAngVel(idx);

    const trunk = pt("trunk");
    const palm = pt("palm");
    const wrist = pt("wrist");
    const elbow = pt("elbow");
    const shoulder = pt("shoulder");

    const boneColor = SKELETON_PALETTE.bone;
    const boneOutline = SKELETON_PALETTE.boneOutline;
    const boneShadow = SKELETON_PALETTE.shadow;

    const drawBone = (a, b, opts = {}) => {
      if (!a || !b) return;
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.shadowColor = opts.shadow || boneShadow;
      ctx.shadowBlur = shadowOff != null ? shadowOff : (opts.blur ?? 12);
      const width = opts.width || 9;
      line(a, b, { color: boneOutline, width: width + 3 });
      line(a, b, { color: opts.color || boneColor, width });
      ctx.restore();
    };

    const useHandHlEarly = Boolean(overlayData?.hand_landmarker_overlay || f?.hand_hl);

    const skel = drawClinicalSkeleton(ctx, {}, {
      pt,
      cw,
      ch,
      drawBone,
      dot,
      line,
      shadowOff,
      affectedSide: overlayData?.affected_side,
      useHandHl: useHandHlEarly,
      phaseColor: { bone: phaseColor.main },
      overlayStyle,
      shoulderWidthPx: Number(overlayData?.shoulder_width_px) || 0,
    });
    const handRoot = skel.palmPt || skel.forearmEnd || pt("wrist");

    const speedThreshold = handPeakV > 0 ? 0.05 * handPeakV : 1.0;
    const inMovement = idx >= win.start_idx && idx <= win.end_idx;
    const t0 = win.start_idx < frames.length ? (frames[win.start_idx].time || win.start_idx / fps) : 0;

    const currentNVP = peakFrames.filter((pi) => pi <= idx).length;

    let currentPeakElbowAngVel = 0;
    let currentMovementTime = 0;
    let currentPauseTime = 0;
    let currentStops = 0;
    let currentStraightness = 0;
    let currentTrunkRatio = 0;

    if (updatePanelMetrics) {
      for (let i = 1; i <= idx && i < frames.length; i++) {
        currentPeakElbowAngVel = Math.max(currentPeakElbowAngVel, getElbowAngVel(i));
      }

      if (inMovement && idx < frames.length) {
        const t = frames[idx].time || idx / fps;
        currentMovementTime = Math.max(0, t - t0);
      }

      for (let i = win.start_idx; i <= idx && i < frames.length; i++) {
        const s = frames[i].speed || 0;
        if (s < speedThreshold) {
          currentPauseTime += 1 / fps;
        }
        if (i > win.start_idx) {
          const prevS = frames[i - 1].speed || 0;
          if (prevS >= speedThreshold && s < speedThreshold) {
            currentStops++;
          }
        }
      }

      if (inMovement) {
        let pathLength = 0;
        const startP = frames[win.start_idx]?.palm;
        for (let i = win.start_idx + 1; i <= idx && i < frames.length; i++) {
          const prev = frames[i - 1]?.palm;
          const curr = frames[i]?.palm;
          if (prev && curr) {
            pathLength += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
          }
        }
        const endP = frames[idx]?.palm;
        if (startP && endP && pathLength > 0) {
          const displacement = Math.hypot(endP[0] - startP[0], endP[1] - startP[1]);
          currentStraightness = Math.min(1, displacement / pathLength);
        }
      }

      if (inMovement) {
        const trunkStart = frames[win.start_idx]?.trunk;
        const trunkEnd = frames[idx]?.trunk;
        const palmStart = frames[win.start_idx]?.palm;
        const palmEnd = frames[idx]?.palm;
        if (trunkStart && trunkEnd && palmStart && palmEnd) {
          const trunkDisp = Math.abs(trunkEnd[0] - trunkStart[0]);
          const palmDisp = Math.hypot(palmEnd[0] - palmStart[0], palmEnd[1] - palmStart[1]);
          if (palmDisp > 0) {
            currentTrunkRatio = Math.min(1, trunkDisp / palmDisp);
          }
        }
      }

      liveMetricsCacheRef.current = {
        idx,
        currentPeakElbowAngVel,
        currentMovementTime,
        currentPauseTime,
        currentStops,
        currentStraightness,
        currentTrunkRatio,
      };
    } else {
      const cached = liveMetricsCacheRef.current;
      if (cached) {
        currentPeakElbowAngVel = cached.currentPeakElbowAngVel ?? 0;
        currentMovementTime = cached.currentMovementTime ?? 0;
        currentPauseTime = cached.currentPauseTime ?? 0;
        currentStops = cached.currentStops ?? 0;
        currentStraightness = cached.currentStraightness ?? 0;
        currentTrunkRatio = cached.currentTrunkRatio ?? 0;
      }
    }

    let currentShoulderElevation = 0;
    if (f && typeof f.shoulder_elevation_norm === "number" && !Number.isNaN(f.shoulder_elevation_norm)) {
      currentShoulderElevation = f.shoulder_elevation_norm;
    }
    let currentShoulderElevationTable = 0;
    if (f && typeof f.shoulder_elevation_table_ratio === "number" && !Number.isNaN(f.shoulder_elevation_table_ratio)) {
      currentShoulderElevationTable = f.shoulder_elevation_table_ratio;
    }
    let currentShoulderElevationPalm = 0;
    if (f && typeof f.shoulder_elevation_palm_ratio === "number" && !Number.isNaN(f.shoulder_elevation_palm_ratio)) {
      currentShoulderElevationPalm = f.shoulder_elevation_palm_ratio;
    }

    const currentElbowAngle = f.elbow_angle || 0;

    let currentShoulderAbduction = 0;
    if (f && typeof f.shoulder_abduction_deg === "number" && f.shoulder_abduction_deg > 0) {
      currentShoulderAbduction = f.shoulder_abduction_deg;
    }
    const adlStart = overlayData?.adl_window?.start_idx ?? win.start_idx;
    let currentFingerQuality = liveMetricsCacheRef.current?.fingerQuality ?? 0;
    let tremorLive = tremorLiveCacheRef.current?.data;
    let adlTremorLive = tremorLiveCacheRef.current?.adlData;
    const resolvedTremor = resolveTremorMetrics(overlayData);

    if (updatePanelMetrics) {
      const fingerQ = computeLiveFingerQuality(frames, adlStart, idx);
      currentFingerQuality = fingerQ ?? 0;
      tremorLive = computeLiveTremorPower(
        frames,
        fps,
        win.start_idx,
        Math.max(win.start_idx, idx),
        overlayData?.shoulder_width_px || 0,
      );
      tremorLiveCacheRef.current = { idx, data: tremorLive };
      if (overlayData?.adl_window) {
        adlTremorLive = computeLiveTremorPower(
          frames,
          fps,
          overlayData.adl_window.start_idx ?? win.start_idx,
          Math.max(overlayData.adl_window.start_idx ?? win.start_idx, idx),
          overlayData?.shoulder_width_px || 0,
        );
        tremorLiveCacheRef.current.adlIdx = idx;
        tremorLiveCacheRef.current.adlData = adlTremorLive;
      }
      liveMetricsCacheRef.current = {
        ...(liveMetricsCacheRef.current || {}),
        fingerQuality: currentFingerQuality,
        idx,
      };
      lastPanelUpdateIdxRef.current = idx;
    }

    const showExtendedKin = false; // UE abduction/finger overlays disabled

    const dpr = overlayCanvasDpr();
    const labelSize = `${Math.round(10 * dpr)}px`;
    const labelPad = 5 * dpr;
    const labelH = Math.round(12 * dpr);

    // Table surface reference line (detected from video frames, independent of color).
    if (overlayData?.table_surface_y != null && overlayData.table_surface_y >= 0 && overlayData.table_surface_y <= 1 && !touchPerf) {
      const ty = overlayData.table_surface_y * ch;
      ctx.save();
      ctx.strokeStyle = "rgba(245,158,11,0.75)";
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 6]);
      ctx.shadowColor = "rgba(245,158,11,0.45)";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(0, ty);
      ctx.lineTo(cw, ty);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      ctx.fillStyle = "rgba(245,158,11,0.95)";
      ctx.font = `600 ${labelSize} sans-serif`;
      const debugText = `Table surface ${overlayData.table_surface_y.toFixed(4)}`;
      ctx.fillText(debugText, 8, Math.max(ty - 6, 14));
    }

    // Shoulder elevation reference is computed server-side; omit vertical guide in player.
    function drawSimpleLabel(text, anchor, offsetX, offsetY, opts = {}) {
      if (!anchor) return;
      const align = opts.align || "left";
      ctx.font = `bold ${labelSize} sans-serif`;
      const tm = ctx.measureText(text);
      const w = tm.width + labelPad * 2;
      const h = labelH + labelPad * 2;
      let x = anchor[0] + offsetX;
      if (align === "center") x = anchor[0] + offsetX - w / 2;
      x = Math.max(4, Math.min(cw - w - 4, x));
      let y = anchor[1] + offsetY;
      y = Math.max(h + 4, Math.min(ch - 4, y));
      ctx.save();
      if (shadowOff === undefined) {
        ctx.shadowColor = "rgba(0,0,0,0.5)";
        ctx.shadowBlur = 8;
      }
      ctx.fillStyle = opts.bg || "rgba(14,17,32,0.85)";
      ctx.strokeStyle = opts.border || "rgba(255,255,255,0.25)";
      ctx.lineWidth = 1;
      const rr = 5;
      ctx.beginPath();
      ctx.moveTo(x + rr, y);
      ctx.lineTo(x + w - rr, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
      ctx.lineTo(x + w, y + h - rr);
      ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
      ctx.lineTo(x + rr, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
      ctx.lineTo(x, y + rr);
      ctx.quadraticCurveTo(x, y, x + rr, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = opts.color || "#fff";
      ctx.fillText(text, x + labelPad, y + h - labelPad - 2);
    }

    const cx = cw / 2;
    if (drawRich) {
      if (shoulder) {
        const shText =
          currentShoulderElevationTable > 0
            ? `Sh ${currentShoulderElevationTable.toFixed(2)}`
            : currentShoulderElevation > 0
            ? `Sh ${currentShoulderElevation.toFixed(2)}`
            : "Sh";
        drawSimpleLabel(shText, shoulder, shoulder[0] > cx ? -110 : 14, -28, { color: color.text, border: color.glow });
        if (showExtendedKin && currentShoulderAbduction > 0) {
          drawSimpleLabel(`Abd ${currentShoulderAbduction.toFixed(0)}${DEG}`, shoulder, shoulder[0] > cx ? -118 : 14, 6, {
            color: "#93c5fd",
            border: "rgba(59,130,246,0.55)",
          });
        }
      }
      if (elbow) {
        drawSimpleLabel(`El ${currentElbowAngle.toFixed(0)}${DEG}`, elbow, elbow[0] > cx ? -80 : 14, -22, { color: color.text, border: color.glow });
      }
      if (palm) {
        drawSimpleLabel(`Ha ${Math.round(speed)} ${DEG}/s`, palm, palm[0] > cx ? -100 : 18, -24, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
        drawSimpleLabel(`NVP ${currentNVP}`, palm, 0, 28, { color: color.text, border: color.glow, align: "center" });
      }
      if (trunk) {
        drawSimpleLabel(`Tr ${(currentTrunkRatio * 100).toFixed(0)}%`, trunk, trunk[0] > cx ? -80 : -80, -52, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
      }
    }

    const useHandHl = useHandHlEarly;
    const fingerTrackConf = Number(f.finger_track_conf);
    const fingerJoints = f.finger_joints || null;
    const fingerVis = f.finger_vis || null;

    const handAccent = color.main || "#10b981";
    const JOINT_DOT = {
      mcp: { fill: handAccent, stroke: "rgba(255,255,255,0.92)", r: 3.1 },
      ip: { fill: color.text || "#6ee7b7", stroke: "rgba(255,255,255,0.9)", r: 3.4 },
      tip: { fill: "#ffffff", stroke: handAccent, r: 3.7 },
    };
    const JOINT_ORDER = ["mcp", "ip", "tip"];

    function jointToCanvas(pair, pairNext) {
      const p = interpPair(pair, pairNext, alpha);
      return p ? [p[0] * cw, p[1] * ch] : null;
    }

    // Pre-v37 overlays re-anchored HL tips onto pose wrist (floated off fingers).
    // Undo: tip' = tip - poseWrist + hlWrist. v37+ / hl_absolute already stores absolute HL.
    const overlayVer = Number(overlayData?.overlay_version) || 0;
    const absHl = overlayData?.finger_coords === "hl_absolute" || overlayVer >= 37;
    const needUndoReanchor = overlayVer > 0 && overlayVer < 37 && !absHl;
    const poseWristPt = pt("wrist");
    const hlWristPt = pt("hl_wrist");
    const elbowPt = pt("elbow");
    const undoReanchor = (cpt) => {
      if (!needUndoReanchor || !cpt || !poseWristPt || !hlWristPt) return cpt;
      return [
        cpt[0] - poseWristPt[0] + hlWristPt[0],
        cpt[1] - poseWristPt[1] + hlWristPt[1],
      ];
    };
    // When Hand Landmarker latches the cup at rest / movement onset, ignore those
    // joints and draw a resting pose-palm hand. Never rotate/scale the cup fan.
    const handSpan = Math.max(1, Math.min(cw, ch));
    const hypotPt = (a, b) => {
      if (!a || !b) return null;
      return Math.hypot(a[0] - b[0], a[1] - b[1]);
    };
    const hlTipsCanvas = [];
    if (fingerJoints) {
      HAND_FINGER_ORDER.forEach((fid) => {
        const fj = fingerJoints[fid];
        if (!fj) return;
        const tip = undoReanchor(jointToCanvas(fj.tip, fNext?.finger_joints?.[fid]?.tip));
        if (tip) hlTipsCanvas.push(tip);
      });
    } else {
      HAND_FINGER_ORDER.forEach((fid) => {
        const tip = undoReanchor(pt(fid));
        if (tip) hlTipsCanvas.push(tip);
      });
    }
    const forearmPx = hypotPt(elbowPt, poseWristPt) || 0;
    const palmReachPx = hypotPt(palm, poseWristPt) || 0;
    const hlOffHand = hlTipsOffPoseHand({
      poseWrist: poseWristPt,
      hlWrist: hlWristPt,
      tips: hlTipsCanvas,
      forearmPx,
      palmReachPx,
      handSpan,
    });

    const sourceState = resolveHandDrawSource(handSourceRef.current, hlOffHand);
    handSourceRef.current = sourceState;
    const drawHl = shouldDrawHlFingers(hlOffHand, sourceState.src);
    if (sourceState.switched) {
      fingerSmoothRef.current = {};
      fingerStickyRef.current = {};
    }

    const restJoints = !drawHl
      ? (buildPoseRestHand(poseWristPt, palm, elbowPt, trunk)?.joints || null)
      : null;

    const smoothStore = fingerSmoothRef.current;
    const smoothFinger = (key, cpt, live) => {
      if (!cpt) return null;
      if (!live) return cpt;
      if (smoothStore._idx != null && Math.abs(idx - smoothStore._idx) > 8) {
        Object.keys(smoothStore).forEach((k) => { if (k !== "_idx") delete smoothStore[k]; });
      }
      smoothStore._idx = idx;
      const prev = smoothStore[key];
      if (!prev) {
        smoothStore[key] = [cpt[0], cpt[1]];
        return cpt;
      }
      // Same-source only, high gain: damps 1px tracker sparkle without trailing
      // the reach and without blending the cup model into the first moving frames.
      const a = 0.78;
      const out = [prev[0] + (cpt[0] - prev[0]) * a, prev[1] + (cpt[1] - prev[1]) * a];
      smoothStore[key] = out;
      return out;
    };

    const jointDots = [];
    const stickyHoldFrames = Math.max(3, Math.round(fps * 0.06));
    const stickyStore = fingerStickyRef.current;
    const pushFingerDot = (fid, jname, cpt, style, live) => {
      if (!cpt) return;
      const key = `${fid}:${jname}`;
      const smoothed = smoothFinger(key, cpt, live);
      if (live) {
        stickyStore[key] = { cpt: [...smoothed], untilIdx: idx + stickyHoldFrames };
        jointDots.push({ fid, jname, cpt: smoothed, style, sticky: false });
        return;
      }
      const held = stickyStore[key];
      if (held && idx <= held.untilIdx) {
        jointDots.push({ fid, jname, cpt: held.cpt, style, sticky: true });
      }
    };

    if (restJoints) {
      HAND_FINGER_ORDER.forEach((fid) => {
        const aj = restJoints[fid];
        if (!aj) return;
        JOINT_ORDER.forEach((jname) => {
          pushFingerDot(fid, jname, aj[jname], JOINT_DOT[jname], true);
        });
      });
    } else if (drawHl && fingerJoints) {
      HAND_FINGER_ORDER.forEach((fid) => {
        const fj = fingerJoints[fid];
        if (!fj) return;
        JOINT_ORDER.forEach((jname) => {
          let cpt = jointToCanvas(fj[jname], fNext?.finger_joints?.[fid]?.[jname]);
          if (!cpt && jname === "tip") cpt = pt(fid);
          cpt = undoReanchor(cpt);
          const coordsOk = Boolean(cpt)
            && cpt[0] > 2 && cpt[1] > 2
            && cpt[0] < cw - 2 && cpt[1] < ch - 2;
          if (!coordsOk) {
            pushFingerDot(fid, jname, cpt, JOINT_DOT[jname], false);
            return;
          }
          const visOk = fj.vis ? fj.vis[jname] !== false : true;
          pushFingerDot(fid, jname, cpt, JOINT_DOT[jname], visOk || Boolean(fj[jname]) || jname === "tip");
        });
      });
    } else if (drawHl) {
      HAND_FINGER_ORDER.forEach((id) => {
        const tipPt = undoReanchor(pt(id));
        const visOk = fingerVis ? fingerVis[id] !== false : true;
        if (tipPt) pushFingerDot(id, "tip", tipPt, JOINT_DOT.tip, visOk || true);
        else pushFingerDot(id, "tip", tipPt, JOINT_DOT.tip, false);
      });
    }

    if (jointDots.length > 0) {
      ctx.save();
      ctx.globalAlpha = useHandHl && Number.isFinite(fingerTrackConf) && fingerTrackConf > 0
        ? Math.min(1, Math.max(0.82, fingerTrackConf))
        : 1;

      if (overlayStyle === "chalk") {
        HAND_FINGER_ORDER.forEach((fid) => {
          const chain = JOINT_ORDER
            .map((jname) => jointDots.find((d) => d.fid === fid && d.jname === jname)?.cpt)
            .filter(Boolean);
          for (let i = 0; i < chain.length - 1; i += 1) {
            drawChalkStick(ctx, chain[i], chain[i + 1], {
              width: 1.55,
              blur: shadowOff != null ? 0 : 3,
              curve: 0.08,
            });
          }
        });
      }

      jointDots.forEach(({ cpt, style, sticky }) => {
        const r = sticky ? Math.max(2.0, style.r * 0.8) : style.r;
        if (overlayStyle === "chalk") {
          drawChalkJoint(ctx, cpt, { r: Math.max(2.2, r * 0.85), dim: sticky });
        } else {
          dot(cpt, {
            fill: sticky ? "rgba(255,255,255,0.55)" : style.fill,
            stroke: style.stroke,
            r,
          });
        }
      });
      ctx.restore();

      if (drawRich && useHandHl) {
        const hlCov = overlayData?.metrics?.hl_index_coverage_pct;
        const anchorPt = jointDots.find((d) => d.fid === "index" && d.jname === "tip")?.cpt
          || jointDots.find((d) => d.jname === "tip")?.cpt;
        if (anchorPt) {
          const hlLabel = hlCov != null && Number.isFinite(Number(hlCov))
            ? `HL ${Math.round(Number(hlCov))}%`
            : fingerTrackConf >= 0.85
              ? "HL"
              : "HL~";
          drawSimpleLabel(hlLabel, anchorPt, anchorPt[0] > cx ? -34 : 8, -18, {
            color: "#c4b5fd",
            border: "rgba(99,102,241,0.55)",
            bg: "rgba(30,27,75,0.82)",
          });
        }
      }

      const indexTip = jointDots.find((d) => d.fid === "index" && d.jname === "tip")?.cpt;
      if (drawRich && showExtendedKin && indexTip && currentFingerQuality > 0) {
        drawSimpleLabel(`Fi ${currentFingerQuality}`, indexTip, indexTip[0] > cx ? -68 : 14, 16, {
          color: "#ddd6fe",
          border: "rgba(167,139,250,0.6)",
        });
      }
    }

        // --- Metric evidence on skeleton: tremor halo + pinch aperture (explains the numbers) ---
    if (drawRich) {
      const fwPx = Number(overlayData?.frame_width_px) || cw;
      const fhPx = Number(overlayData?.frame_height_px) || ch;
      const swPx = Number(overlayData?.shoulder_width_px) || 0;
      const tremorAnchor = palm || pt("wrist") || pt("hl_wrist");

      // Tremor: pulsing halo sized by local 8?12 Hz envelope / short-window activity
      if (tremorAnchor && idx >= win.start_idx && idx <= win.end_idx) {
        const env = localTremorEnvelopeAt(overlayData, idx);
        const act = localTremorActivity(frames, idx, fps, swPx);
        const intensity = env != null ? Math.min(1, env * 4) : act != null ? Math.min(1, act * 12) : 0;
        const livePow =
          idx >= win.end_idx
            ? resolvedTremor?.tremor_8_12hz_power
            : tremorLive?.tremor_8_12hz_power ?? resolvedTremor?.tremor_8_12hz_power;
        const peakHz =
          idx >= win.end_idx
            ? resolvedTremor?.tremor_peak_freq_hz
            : tremorLive?.tremor_peak_freq_hz ?? resolvedTremor?.tremor_peak_freq_hz;
        if (intensity > 0.02 || livePow != null) {
          const r = 14 + intensity * 42;
          const alphaHalo = 0.12 + intensity * 0.55;
          ctx.save();
          ctx.beginPath();
          ctx.arc(tremorAnchor[0], tremorAnchor[1], r, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(251,113,133,${Math.min(0.95, alphaHalo).toFixed(2)})`;
          ctx.lineWidth = 2.5 + intensity * 3;
          ctx.shadowColor = "rgba(251,113,133,0.65)";
          ctx.shadowBlur = 12 + intensity * 18;
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(tremorAnchor[0], tremorAnchor[1], Math.max(6, r * 0.45), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(251,113,133,${(0.08 + intensity * 0.28).toFixed(2)})`;
          ctx.fill();
          ctx.restore();
          drawSimpleLabel(
            `Tr ${formatTremorPower(livePow)}${peakHz != null ? ` \u00b7 ${Number(peakHz).toFixed(1)}Hz` : ""}`,
            tremorAnchor,
            tremorAnchor[0] > cx ? -150 : 20,
            -52,
            { color: "#fda4af", border: "rgba(251,113,133,0.55)", bg: "rgba(40,10,18,0.85)" },
          );
          if (showExtendedKin || livePow != null) {
            drawEvidenceCard(
              ctx,
              buildTremorEvidenceLines(overlayData, livePow, peakHz),
              tremorAnchor,
              {
                cw,
                ch,
                dpr,
                offsetX: tremorAnchor[0] > cx ? -210 : 18,
                offsetY: -118,
                border: "rgba(251,113,133,0.4)",
                titleColor: "#fecdd3",
              },
            );
          }
        }
      }

      // Pinch line: HL thumb/index tips only (never pose thumb/index ? those sit on the cup at t=0).
      const thumbTip = jointDots.find((d) => d.fid === "thumb" && d.jname === "tip")?.cpt;
      const indexTipEv = jointDots.find((d) => d.fid === "index" && d.jname === "tip")?.cpt;
      const fingerActive = idx >= win.start_idx && idx <= win.end_idx && idx > win.start_idx;
      if (fingerActive && thumbTip && indexTipEv) {
        const liveAp = pinchApertureFromFrame(f, fwPx, fhPx, swPx);
        const winStats = pinchApertureWindowStats(frames, win, fwPx, fhPx, swPx);
        const q = pickOverlayMetric(overlayData, ["pinch_grasp_quality_index", "adl_pinch_grasp_quality_index"]);
        const qN = q != null ? Number(q) : null;
        const lineCol =
          qN != null && Number.isFinite(qN)
            ? qN >= 70
              ? "rgba(52,211,153,0.95)"
              : qN >= 40
                ? "rgba(251,191,36,0.95)"
                : "rgba(251,113,133,0.95)"
            : "rgba(167,139,250,0.95)";

        ctx.save();
        ctx.strokeStyle = lineCol;
        ctx.lineWidth = 3;
        ctx.shadowColor = lineCol;
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.moveTo(thumbTip[0], thumbTip[1]);
        ctx.lineTo(indexTipEv[0], indexTipEv[1]);
        ctx.stroke();
        ctx.restore();
        const mid = [(thumbTip[0] + indexTipEv[0]) / 2, (thumbTip[1] + indexTipEv[1]) / 2];
        const apLabel =
          liveAp?.apertureSw != null
            ? `Pinch ${liveAp.apertureSw.toFixed(3)} SW`
            : "Pinch";
        drawSimpleLabel(apLabel, mid, mid[0] > cx ? -120 : 12, -10, {
          color: "#e9d5ff",
          border: "rgba(167,139,250,0.55)",
          bg: "rgba(30,20,50,0.88)",
        });
        if (qN != null && Number.isFinite(qN)) {
          drawSimpleLabel(`Grasp Q ${Math.round(qN)}`, mid, mid[0] > cx ? -110 : 12, 14, {
            color: qN >= 70 ? "#6ee7b7" : qN >= 40 ? "#fde68a" : "#fda4af",
            border: "rgba(167,139,250,0.45)",
            bg: "rgba(30,20,50,0.88)",
          });
        }
        drawEvidenceCard(
          ctx,
          buildPinchEvidenceLines(overlayData, liveAp?.apertureSw, winStats?.romSw),
          mid,
          {
            cw,
            ch,
            dpr,
            offsetX: mid[0] > cx ? -230 : 16,
            offsetY: 36,
            border: "rgba(167,139,250,0.4)",
            titleColor: "#e9d5ff",
          },
        );
      }
    }

    if (drawRich) {
    const startPt = toCanvas(startPalm);
    const endPt = toCanvas(endPalm);

    if (idx >= win.start_idx && idx <= win.end_idx) {
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.shadowColor = "rgba(16,185,129,0.6)";
      ctx.shadowBlur = 16;
      ctx.lineWidth = 6;
      ctx.strokeStyle = "rgba(16,185,129,0.95)";
      ctx.beginPath();
      let first = true;
      for (let i = win.start_idx; i <= idx; i++) {
        const tf = frames[i]?.palm;
        if (!tf) { continue; }
        const tp = toCanvas(tf);
        if (!tp) { continue; }
        const tx = tp[0];
        const ty = tp[1];
        if (first) {
          ctx.moveTo(tx, ty);
          first = false;
        } else {
          ctx.lineTo(tx, ty);
        }
      }
      ctx.stroke();
      ctx.restore();

      if (palm) {
        dot([palm[0], palm[1]], { fill: "#fff", stroke: "#10b981", r: 3.5 });
      }
    }
    if (startPt) {
      dot(startPt, { fill: "#facc15", stroke: "#fff", r: 7 });
      drawSimpleLabel("Start", startPt, startPt[0] > cx ? -52 : 20, 26, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
    }
    if (endPt) {
      dot(endPt, { fill: "#10b981", stroke: "#fff", r: 7 });
      drawSimpleLabel("End", endPt, endPt[0] > cx ? -46 : 20, 26, { color: "#6ee7b7", border: "rgba(16,185,129,0.6)" });
    }

    const traceFrames = Math.max(12, Math.round(fps * 0.6));
    const traceStart = Math.max(0, idx - traceFrames);
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.shadowColor = "rgba(250,204,21,0.40)";
    ctx.shadowBlur = 10;
    ctx.lineWidth = 5;
    let prev = null;
    for (let i = traceStart; i <= idx; i += 1) {
      const tf = frames[i]?.palm;
      if (!tf) { prev = null; continue; }
      const tp = toCanvas(tf);
      if (!tp) { prev = null; continue; }
      const tx = tp[0];
      const ty = tp[1];
      const alpha = 0.25 + 0.7 * ((i - traceStart) / Math.max(1, idx - traceStart));
      ctx.strokeStyle = `rgba(250,204,21,${Math.min(0.95, alpha).toFixed(2)})`;
      if (prev) {
        ctx.beginPath();
        ctx.moveTo(prev[0], prev[1]);
        ctx.lineTo(tx, ty);
        ctx.stroke();
      }
      prev = [tx, ty];
    }
    ctx.restore();
    }

    if (idx >= win.start_idx && idx <= win.end_idx && drawRich) {
      ctx.save();
      ctx.strokeStyle = color.glow;
      ctx.lineWidth = 3;
      ctx.shadowColor = color.main;
      ctx.shadowBlur = 10;
      ctx.strokeRect(5, 5, cw - 10, ch - 10);
      ctx.restore();
    }

    // Always refresh bake HUD while recording so Drive video matches the product panel.
    {
      const liveBake = {
        straightness: currentStraightness,
        peakElbowAngVel: currentPeakElbowAngVel,
        movementTime: currentMovementTime,
        pauseTime: currentPauseTime,
        stops: currentStops,
        trunkRatio: currentTrunkRatio,
        shoulderElevation: currentShoulderElevation,
        shoulderElevationTable: currentShoulderElevationTable,
        shoulderElevationPalm: currentShoulderElevationPalm,
        shoulderAbduction: currentShoulderAbduction,
        fingerQuality: currentFingerQuality,
        tremor_8_12hz_power:
          idx >= win.end_idx
            ? resolvedTremor?.tremor_8_12hz_power
            : tremorLive?.tremor_8_12hz_power ?? resolvedTremor?.tremor_8_12hz_power,
        tremor_index:
          idx >= win.end_idx
            ? resolvedTremor?.tremor_index
            : tremorLive?.tremor_index ?? resolvedTremor?.tremor_index,
        index_tremor_8_12hz_power: resolvedTremor?.index_tremor_8_12hz_power,
        tremor_peak_freq_hz:
          idx >= win.end_idx
            ? resolvedTremor?.tremor_peak_freq_hz
            : tremorLive?.tremor_peak_freq_hz ?? resolvedTremor?.tremor_peak_freq_hz,
        movement_quality_index: overlayData?.metrics?.movement_quality_index
          ?? pickOverlayMetric(overlayData, ["movement_quality_index"]),
        adl_tremor_8_12hz_power:
          adlTremorLive?.tremor_8_12hz_power
          ?? resolvedTremor?.adl_tremor_8_12hz_power
          ?? tremorLive?.tremor_8_12hz_power
          ?? resolvedTremor?.tremor_8_12hz_power,
      };
      if (baking) {
        bakeHudRef.current = {
          phaseLabel,
          nvp: currentNVP,
          color,
          live: liveBake,
          rowDefs: getValidationPanelRowDefs(overlayData, clinicalTask),
          idx,
          velocityProfile,
          elbowProfile: overlayData?.elbow_angle_profile,
          trunkProfile: overlayData?.trunk_x_profile,
          overlayData,
          formatValue,
        };
      }
    }

    if (useExternalPanel && (updatePanelMetrics || lastPanelUpdateIdxRef.current === idx)) {
      const live = {
        straightness: currentStraightness,
        peakElbowAngVel: currentPeakElbowAngVel,
        movementTime: currentMovementTime,
        pauseTime: currentPauseTime,
        stops: currentStops,
        trunkRatio: currentTrunkRatio,
        shoulderElevation: currentShoulderElevation,
        shoulderElevationTable: currentShoulderElevationTable,
        shoulderElevationPalm: currentShoulderElevationPalm,
        shoulderAbduction: currentShoulderAbduction,
        fingerQuality: currentFingerQuality,
        tremor_8_12hz_power:
          idx >= win.end_idx
            ? resolvedTremor?.tremor_8_12hz_power
            : tremorLive?.tremor_8_12hz_power ?? resolvedTremor?.tremor_8_12hz_power,
        tremor_index:
          idx >= win.end_idx
            ? resolvedTremor?.tremor_index
            : tremorLive?.tremor_index ?? resolvedTremor?.tremor_index,
        index_tremor_8_12hz_power: resolvedTremor?.index_tremor_8_12hz_power,
        tremor_peak_freq_hz:
          idx >= win.end_idx
            ? resolvedTremor?.tremor_peak_freq_hz
            : tremorLive?.tremor_peak_freq_hz ?? resolvedTremor?.tremor_peak_freq_hz,
        movement_quality_index: overlayData?.metrics?.movement_quality_index
          ?? pickOverlayMetric(overlayData, ["movement_quality_index"]),
        adl_tremor_8_12hz_power:
          adlTremorLive?.tremor_8_12hz_power
          ?? resolvedTremor?.adl_tremor_8_12hz_power
          ?? tremorLive?.tremor_8_12hz_power
          ?? resolvedTremor?.tremor_8_12hz_power,
      };
      const rowDefs = getValidationPanelRowDefs(overlayData, clinicalTask);

      if (panelPhaseRef.current) {
        panelPhaseRef.current.textContent = `${phaseLabel || "Trial"}`;
      }
      if (panelNvpRef.current) {
        panelNvpRef.current.textContent = `NVP ${currentNVP}`;
        panelNvpRef.current.style.color = color.text;
      }
      rowDefs.forEach((row, i) => {
        const el = panelMetricValueRefs.current[i];
        if (!el) return;
        el.textContent = formatPanelRowValue(row, live, overlayData, formatValue);
        el.style.color = row.accent ? color.text : "rgba(255,255,255,0.94)";
      });

      const showHand = velocityProfile?.t?.length >= 2;
      const showElbow = Boolean(overlayData?.elbow_angle_profile?.t?.length);
      const showTrunk = Boolean(overlayData?.trunk_x_profile?.t?.length);
      if (chartHandWrapRef.current) chartHandWrapRef.current.classList.toggle("hidden", !showHand);
      if (chartElbowWrapRef.current) chartElbowWrapRef.current.classList.toggle("hidden", !showElbow);
      if (chartTrunkWrapRef.current) chartTrunkWrapRef.current.classList.toggle("hidden", !showTrunk);
      if (showHand && updatePanelCharts) drawPanelChartLine(chartHandRef.current, velocityProfile, idx, color.main, false);
      if (showElbow && updatePanelCharts) drawPanelChartLine(chartElbowRef.current, overlayData?.elbow_angle_profile, idx, "#7dd3fc", true);
      if (showTrunk && updatePanelCharts) drawPanelChartLine(chartTrunkRef.current, overlayData?.trunk_x_profile, idx, "#facc15", true);
    } else if (!touchPerf && !baking) {
    // Inline fallback panel (drawn on video canvas when gutter is narrow ? skipped on iPad for performance)
    // Skipped during Drive bake: product side-panel is composited in drawRecordingFrame instead.
    const unscaledPad = 8 * dpr;
    let fsSmall = `${Math.round(8 * dpr)}px`;
    const unscaledPanelW = Math.max(52 * dpr, Math.min(200 * dpr, cw * 0.45));
    const unscaledChartH = 30 * dpr;
    const unscaledRowH = 14 * dpr;
    const unscaledHeaderH = 26 * dpr;
    const unscaledHeaderGap = 22 * dpr;
    const unscaledPanelH = unscaledHeaderH + unscaledHeaderGap + unscaledRowH * 13 + unscaledChartH * 3 + unscaledPad * 2 + 20;
    const maxPanelH = ch - unscaledPad * 2;
    const panelScale = unscaledPanelH > maxPanelH ? Math.max(0.65, maxPanelH / unscaledPanelH) : 1;
    const pad = unscaledPad * panelScale;
    const panelW = unscaledPanelW * panelScale;
    const panelX = cw - panelW - pad;
    const panelY = pad;
    const panelHFit = Math.min(unscaledPanelH * panelScale, ch - pad * 2);
    const chartH = unscaledChartH * panelScale;
    const rowH = unscaledRowH * panelScale;
    const headerH = unscaledHeaderH * panelScale;
    const headerGap = unscaledHeaderGap * panelScale;
    const px = panelX;
    const py = panelY;
    const pw = panelW;
    const outerR = 10 * dpr * panelScale;
    const rowGap = 3 * dpr;

    drawPanelCardRect(panelCtx, px, py, pw, panelHFit, outerR);

    const left = px + pad;
    const right = px + pw - pad;
    const contentW = pw - pad * 2;
    const fsLabel = `${Math.round(11 * dpr * panelScale)}px`;
    const fsMain = `${Math.round(12 * dpr * panelScale)}px`;
    fsSmall = fsLabel;

    panelCtx.font = `bold ${Math.round(13 * dpr * panelScale)}px sans-serif`;
    panelCtx.fillStyle = "#fff";
    panelCtx.textAlign = "left";
    panelCtx.fillText(`${phaseLabel || "Trial"}`, left, py + headerH / 2 + 5);
    panelCtx.fillStyle = color.text;
    panelCtx.textAlign = "right";
    panelCtx.fillText(`NVP ${currentNVP}`, right, py + headerH / 2 + 5);
    panelCtx.textAlign = "left";

    const liveInline = {
      straightness: currentStraightness,
      peakElbowAngVel: currentPeakElbowAngVel,
      movementTime: currentMovementTime,
      pauseTime: currentPauseTime,
      stops: currentStops,
      trunkRatio: currentTrunkRatio,
      shoulderElevation: currentShoulderElevation,
      shoulderElevationTable: currentShoulderElevationTable,
      shoulderElevationPalm: currentShoulderElevationPalm,
      shoulderAbduction: currentShoulderAbduction,
      fingerQuality: currentFingerQuality,
    };
    const rowDefsInline = getValidationPanelRowDefs(overlayData, clinicalTask);

    let cy = py + headerH + headerGap;
    rowDefsInline.forEach((row) => {
      const valueText = formatPanelRowValue(row, liveInline, overlayData, formatValue);
      const cardH = Math.max(18 * dpr, rowH + rowGap);
      const textY = cy + cardH * 0.68;
      panelCtx.font = `700 ${fsLabel} sans-serif`;
      panelCtx.fillStyle = "rgba(255,255,255,0.78)";
      panelCtx.fillText(row.label, left, textY);
      panelCtx.font = `bold ${fsMain} sans-serif`;
      panelCtx.fillStyle = row.accent ? color.text : "rgba(255,255,255,0.95)";
      panelCtx.textAlign = "right";
      panelCtx.fillText(valueText, right, textY);
      panelCtx.textAlign = "left";
      cy += cardH;
    });

    const gw = Math.min(170 * window.devicePixelRatio, cw * 0.42);
    const gh = 8 * window.devicePixelRatio;
    const overlayPad = 8 * window.devicePixelRatio;
    const gx = cw - gw - overlayPad;
    const gy = ch - 34 * window.devicePixelRatio;
    const speedPct = peakV > 0 ? Math.min(1, speed / peakV) : 0;

    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.10)";
    ctx.shadowBlur = 6;
    ctx.shadowOffsetY = 2;
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    ctx.strokeStyle = "rgba(255,255,255,0.28)";
    ctx.lineWidth = 1;
    const gpx = gx - 6, gpy = gy - 16, gpw = gw + 12, gph = gh + 22;
    ctx.beginPath();
    ctx.moveTo(gpx + 8, gpy);
    ctx.lineTo(gpx + gpw - 8, gpy);
    ctx.quadraticCurveTo(gpx + gpw, gpy, gpx + gpw, gpy + 8);
    ctx.lineTo(gpx + gpw, gpy + gph - 8);
    ctx.quadraticCurveTo(gpx + gpw, gpy + gph, gpx + gpw - 8, gpy + gph);
    ctx.lineTo(gpx + 8, gpy + gph);
    ctx.quadraticCurveTo(gpx, gpy + gph, gpx, gpy + gph - 8);
    ctx.lineTo(gpx, gpy + 8);
    ctx.quadraticCurveTo(gpx, gpy, gpx + 8, gpy);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    ctx.fillStyle = "rgba(255,255,255,0.18)";
    ctx.fillRect(gx, gy, gw, gh);
    const grad = ctx.createLinearGradient(gx, 0, gx + gw, 0);
    grad.addColorStop(0, "rgba(16,185,129,0.95)");
    grad.addColorStop(0.5, "rgba(250,204,21,0.95)");
    grad.addColorStop(1, "rgba(244,63,94,0.95)");
    ctx.fillStyle = grad;
    ctx.fillRect(gx, gy, gw * speedPct, gh);
    ctx.fillStyle = "#fff";
    ctx.font = `bold ${fsSmall} sans-serif`;
    ctx.fillText(`Speed ${Math.round(speed)} ?/s`, gx, gy - 4);
    }

  }, [frames, fps, win, peakV, handPeakV, startPalm, endPalm, velocityProfile, phaseColor, phaseLabel, getFrameIndex, getFrameState, peakFrames, getElbowAngVel, overlayData?.elbow_angle_profile, overlayData?.trunk_x_profile, overlayData?.table_surface_y, overlayData?.shoulder_palm_anchor, overlayData, clinicalTask, isExpanded, overlayStyle, smoothTracks]);

  const renderBakeOverlayNative = useCallback(() => {
    if (!bakeOverlayCanvasRef.current) {
      const el = document.createElement("canvas");
      bakeOverlayCanvasRef.current = el;
    }
    bakeOverlayPassRef.current = true;
    try {
      drawOverlay();
    } finally {
      bakeOverlayPassRef.current = false;
    }
    return bakeOverlayCanvasRef.current;
  }, [drawOverlay]);

  const drawRecordingFrame = useCallback(() => {
    const video = videoRef.current;
    const recCanvas = recCanvasRef.current;
    if (!video || !recCanvas) return;
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    const gap = Math.max(10, Math.round(vw * 0.01));
    const panelW = Math.round(Math.min(Math.max(vw * 0.36, 280), Math.max(360, vw * 0.42)));
    const outW = vw + gap + panelW;
    const outH = vh;
    const scale = 2;
    if (recCanvas.width !== outW * scale || recCanvas.height !== outH * scale) {
      recCanvas.width = outW * scale;
      recCanvas.height = outH * scale;
    }
    const ctx = recCanvas.getContext("2d", { alpha: false, desynchronized: true });
    if (!ctx) return;
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.fillStyle = "#121820";
    ctx.fillRect(0, 0, outW, outH);
    ctx.drawImage(video, 0, 0, vw, vh);
    const bakeOv = renderBakeOverlayNative();
    if (bakeOv) ctx.drawImage(bakeOv, 0, 0, vw, vh);
    drawBakeProductPanel(ctx, vw + gap, 0, panelW, outH, bakeHudRef.current);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }, [renderBakeOverlayNative]);

  const getSupportedMimeType = () => {
    const types = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8,opus",
      "video/webm;codecs=vp8",
      "video/webm",
      "video/mp4",
    ];
    return types.find((t) => MediaRecorder.isTypeSupported(t)) || "video/webm";
  };

  const estimateBakeBitrate = useCallback(async (video) => {
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    const panelW = Math.round(Math.min(Math.max(vw * 0.36, 280), Math.max(360, vw * 0.42)));
    const gap = Math.max(10, Math.round(vw * 0.01));
    const pixels = Math.max(1, (vw + gap + panelW) * vh * 4);
    const captureFps = Math.min(60, Math.max(24, Math.round(Number(fps) || 30)));
    let bps = Math.round(pixels * captureFps * 0.28);
    try {
      if (videoUrl) {
        const res = await fetch(videoUrl);
        if (res.ok) {
          const blob = await res.blob();
          const dur = Math.max(0.5, Number(video.duration) || 1);
          if (blob.size > 5000) {
            bps = Math.max(bps, Math.round((blob.size * 8) / dur * 2.2));
          }
        }
      }
    } catch {
      /* use pixel estimate */
    }
    return {
      videoBitsPerSecond: Math.min(160_000_000, Math.max(32_000_000, bps)),
      captureFps,
    };
  }, [fps, videoUrl]);

  const startRecording = useCallback(async () => {
    const video = videoRef.current;
    const recCanvas = recCanvasRef.current;
    if (!video || !recCanvas) return;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") return;
    recordingRef.current = true;
    fingerStickyRef.current = {};
    fingerSmoothRef.current = {};
    handSourceRef.current = { src: "pose", offStreak: 0, onStreak: 0 };
    // Keep the live overlay in display space. Baking used to switch the visible
    // canvas to native pixels, which threw chalk off the hand for the first plays.
    drawOverlay();
    drawRecordingFrame();
    const { videoBitsPerSecond, captureFps } = await estimateBakeBitrate(video);
    const stream = recCanvas.captureStream(captureFps);
    const mimeType = getSupportedMimeType();
    let recorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond });
    } catch {
      try {
        recorder = new MediaRecorder(stream, { mimeType, bitsPerSecond: videoBitsPerSecond });
      } catch {
        recorder = new MediaRecorder(stream, { mimeType });
      }
    }
    mediaRecorderRef.current = recorder;
    recordedChunksRef.current = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      recordingRef.current = false;
      fingerStickyRef.current = {};
      fingerSmoothRef.current = {};
      handSourceRef.current = { src: "pose", offStreak: 0, onStreak: 0 };
      if (video) video.playbackRate = playbackRate || 1;
      const blob = new Blob(recordedChunksRef.current, { type: mimeType.includes("mp4") ? "video/mp4" : "video/webm" });
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      onDownloadReady?.(url, blob);
      setRecording(false);
      setDownloadBusy(false);
      requestAnimationFrame(() => {
        drawOverlay();
      });
    };
    recorder.start(250);
    setRecording(true);
    video.muted = true;
    video.playbackRate = 1;
    try {
      video.currentTime = 0;
      await video.play();
    } catch (err) {
      recordingRef.current = false;
      try {
        if (recorder.state === "recording") recorder.stop();
      } catch {
        /* ignore */
      }
      setRecording(false);
      setDownloadBusy(false);
      onError?.(err?.message || "Could not start screen record");
    }
  }, [drawOverlay, drawRecordingFrame, estimateBakeBitrate, onDownloadReady, onError, playbackRate]);

  const stopRecording = useCallback(() => {
    const rec = mediaRecorderRef.current;
    if (rec && rec.state === "recording") {
      try { rec.stop(); } catch { /* ignore */ }
    }
  }, []);

  const handleScreenRecord = useCallback(async () => {
    if (recording || mediaRecorderRef.current?.state === "recording") {
      stopRecording();
      return;
    }
    if (downloadBusy) return;
    setDownloadBusy(true);
    try {
      pendingDownloadRef.current = false;
      await startRecording();
    } catch (err) {
      onError?.(err?.message || "Screen record failed");
      setDownloadBusy(false);
    }
  }, [recording, downloadBusy, startRecording, stopRecording, onError]);

  const tryAutoRender = useCallback(() => {
    const video = videoRef.current;
    if (
      !autoRender ||
      autoRenderStartedRef.current ||
      mediaRecorderRef.current?.state === "recording" ||
      downloadUrl ||
      !video ||
      video.readyState < 1 ||
      !frames.length
    ) {
      return;
    }
    autoRenderStartedRef.current = true;
    startRecording();
  }, [autoRender, downloadUrl, frames.length, startRecording]);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    const useVfc = typeof video.requestVideoFrameCallback === "function";
    let rafActive = false;

    const runPaint = () => {
      videoTimeRef.current = video.currentTime ?? 0;
      lastPaintMediaTimeRef.current = videoTimeRef.current;
      drawOverlay();
      if (recording) drawRecordingFrame();
    };

    const schedulePaint = () => {
      if (!videoRef.current || !canvasRef.current) return;
      const touchLive = isCoarsePointerDevice();
      if (touchLive && !videoRef.current.paused) {
        runPaint();
        return;
      }
      if (paintPendingRef.current) return;
      paintPendingRef.current = true;
      requestAnimationFrame(() => {
        paintPendingRef.current = false;
        if (!videoRef.current || !canvasRef.current) return;
        runPaint();
      });
    };

    const scheduleProgress = () => {
      if (progressRafRef.current) return;
      progressRafRef.current = requestAnimationFrame(() => {
        progressRafRef.current = 0;
        const pct = video.duration ? (video.currentTime / video.duration) * 100 : 0;
        setProgress(pct);
        setDisplayTime(video.currentTime || 0);
        setDisplayDuration(video.duration || 0);
        if (recording) setRenderProgress(pct);
      });
    };

    const stopRafLoop = () => {
      rafActive = false;
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    const rafLoop = () => {
      if (!rafActive || video.paused) {
        rafRef.current = null;
        return;
      }
      schedulePaint();
      rafRef.current = requestAnimationFrame(rafLoop);
    };

    const startRafLoop = () => {
      if (rafActive || useVfc) return;
      rafActive = true;
      rafRef.current = requestAnimationFrame(rafLoop);
    };

    const stopVfc = () => {
      if (vfcIdRef.current && video.cancelVideoFrameCallback) {
        video.cancelVideoFrameCallback(vfcIdRef.current);
        vfcIdRef.current = null;
      }
    };

    const onVideoFrame = (_now, metadata) => {
      videoTimeRef.current = metadata?.mediaTime ?? video.currentTime ?? 0;
      schedulePaint();
      scheduleProgress();
      if (!video.paused && useVfc) {
        vfcIdRef.current = video.requestVideoFrameCallback(onVideoFrame);
      }
    };

    const onLoadedMetadata = () => {
      canvasLayoutCacheRef.current = { key: "", result: null };
      gutterLayoutCacheRef.current = { key: "", result: null };
      const vw = video.videoWidth || 1;
      const vh = video.videoHeight || 1;
      setVideoAspect(vw / vh);
      checkOverlaySource(vw, vh, video.duration);
      videoTimeRef.current = video.currentTime ?? 0;
      lastPaintMediaTimeRef.current = -1;
      setDisplayDuration(video.duration || 0);
      setDisplayTime(video.currentTime || 0);
      schedulePaint();
      tryAutoRender();
    };

    const onLoadedData = () => {
      canvasLayoutCacheRef.current = { key: "", result: null };
      gutterLayoutCacheRef.current = { key: "", result: null };
      lastPaintMediaTimeRef.current = -1;
      schedulePaint();
    };

    const onTimeUpdate = () => {
      videoTimeRef.current = video.currentTime ?? 0;
      scheduleProgress();
      if (video.paused) schedulePaint();
    };

    const onPlay = () => {
      setIsPlaying(true);
      lastPaintMediaTimeRef.current = -1;
      if (useVfc) {
        stopRafLoop();
        vfcIdRef.current = video.requestVideoFrameCallback(onVideoFrame);
      } else {
        startRafLoop();
      }
    };

    const onPause = () => {
      setIsPlaying(false);
      stopVfc();
      stopRafLoop();
      videoTimeRef.current = video.currentTime ?? 0;
      lastPaintMediaTimeRef.current = -1;
      schedulePaint();
    };

    const onVideoEnded = () => {
      setIsPlaying(false);
      stopVfc();
      stopRafLoop();
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      onEnded?.();
    };

    const onResize = () => {
      canvasLayoutCacheRef.current = { key: "", result: null };
      gutterLayoutCacheRef.current = { key: "", result: null };
      lastPaintMediaTimeRef.current = -1;
      schedulePaint();
    };

    video.addEventListener("loadedmetadata", onLoadedMetadata);
    video.addEventListener("loadeddata", onLoadedData);
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("ended", onVideoEnded);
    window.addEventListener("resize", onResize);

    if (!video.paused) onPlay();
    else schedulePaint();

    return () => {
      video.removeEventListener("loadedmetadata", onLoadedMetadata);
      video.removeEventListener("loadeddata", onLoadedData);
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("ended", onVideoEnded);
      window.removeEventListener("resize", onResize);
      stopVfc();
      stopRafLoop();
      if (progressRafRef.current) cancelAnimationFrame(progressRafRef.current);
    };
  }, [videoUrl, drawOverlay, drawRecordingFrame, recording, onEnded, tryAutoRender, checkOverlaySource]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !autoPlay) return;
    video.muted = true;
    video.play().catch(() => {});
  }, [videoUrl, autoPlay]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      setIsPlaying(true);
      video.play().catch(() => setIsPlaying(false));
    } else {
      setIsPlaying(false);
      video.pause();
    }
  };

  const controlTap = (handler) => (e) => {
    e.stopPropagation();
    if (typeof e.preventDefault === "function" && e.cancelable) {
      try { e.preventDefault(); } catch (_) { /* iOS */ }
    }
    handler(e);
  };

  const applySeekFromEvent = (e, el) => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    const rect = el.getBoundingClientRect();
    const clientX = e.clientX ?? e.nativeEvent?.changedTouches?.[0]?.clientX;
    if (clientX == null) return;
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const nextTime = pct * video.duration;
    video.currentTime = nextTime;
    videoTimeRef.current = nextTime;
    setDisplayTime(nextTime);
    setProgress(pct * 100);
    lastPaintMediaTimeRef.current = -1;
    fingerStickyRef.current = {};
    fingerSmoothRef.current = {};
    handSourceRef.current = { src: "pose", offStreak: 0, onStreak: 0 };
    drawOverlay();
  };

  /** Tap video stage to play/pause (ignore control chrome). */
  const onVideoSurfacePointerUp = (e) => {
    if (e.button != null && e.button !== 0) return;
    const t = e.target;
    if (!(t instanceof Element)) return;
    if (t.closest(".validation-player-controls, .validation-control-btn, .validation-seek-bar, .validation-player-topbar")) {
      return;
    }
    // Ignore lingering multi-touch / drag
    if (e.pointerType === "touch" && typeof e.detail === "number" && e.detail > 1) return;
    togglePlay();
  };

  const handleSeek = (e) => {
    applySeekFromEvent(e, e.currentTarget);
  };

  useEffect(() => {
    const mq = window.matchMedia("(pointer: coarse)");
    const syncTouch = () => {
      setIsTouchUi(mq.matches || navigator.maxTouchPoints > 0);
    };
    syncTouch();
    mq.addEventListener?.("change", syncTouch);
    return () => mq.removeEventListener?.("change", syncTouch);
  }, []);

  const exitExpanded = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      savedTimeRef.current = video.currentTime || 0;
      wasPlayingRef.current = !video.paused;
    }
    setIsExpanded(false);
  }, []);

  const requestFullscreen = () => {
    if (isExpanded) {
      exitExpanded();
      return;
    }
    const video = videoRef.current;
    if (video) {
      savedTimeRef.current = video.currentTime || 0;
      wasPlayingRef.current = !video.paused;
    }
    setIsExpanded(true);
  };

  useEffect(() => {
    if (!isExpanded) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e) => {
      if (e.key === "Escape") exitExpanded();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [isExpanded, exitExpanded]);

  const toggleSpeed = () => {
    const speeds = [0.5, 1, 1.5, 2];
    const idx = speeds.indexOf(playbackRate);
    const next = speeds[(idx + 1) % speeds.length];
    setPlaybackRate(next);
  };

  const stepFrame = (dir) => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    video.pause();
    const step = dir / fps;
    const nextTime = Math.max(0, Math.min(video.duration, video.currentTime + step));
    video.currentTime = nextTime;
    videoTimeRef.current = nextTime;
    setIsPlaying(false);
    setDisplayTime(nextTime);
    setProgress(video.duration ? (nextTime / video.duration) * 100 : 0);
    lastPaintMediaTimeRef.current = -1;
    fingerStickyRef.current = {};
    fingerSmoothRef.current = {};
    handSourceRef.current = { src: "pose", offStreak: 0, onStreak: 0 };
    drawOverlay();
  };

  const formatTime = (s) => {
    if (!s || isNaN(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  useEffect(() => {
    lastPaintMediaTimeRef.current = -1;
    drawOverlay();
  }, [overlayStyle, drawOverlay]);

  useEffect(() => {
    autoRenderStartedRef.current = false;
    setDownloadUrl(null);
    setRenderProgress(0);
  }, [videoUrl]);

  useEffect(() => {
    tryAutoRender();
  }, [tryAutoRender]);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      canvasLayoutCacheRef.current = { key: "", result: null };
      gutterLayoutCacheRef.current = { key: "", result: null };
      drawOverlay();
      window.dispatchEvent(new Event("resize"));
    });
    return () => cancelAnimationFrame(id);
  }, [isExpanded, drawOverlay]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const target = savedTimeRef.current;
    const shouldPlay = wasPlayingRef.current;
    const apply = () => {
      if (Number.isFinite(target) && target >= 0) {
        const cur = video.currentTime || 0;
        if (Math.abs(cur - target) > 0.08) video.currentTime = target;
      }
      setDisplayTime(video.currentTime || target || 0);
      setDisplayDuration(video.duration || 0);
      setProgress(video.duration ? ((video.currentTime || 0) / video.duration) * 100 : 0);
      if (shouldPlay) video.play().catch(() => {});
      else video.pause();
    };
    if (video.readyState >= 1) apply();
    else video.addEventListener("loadeddata", apply, { once: true });
    return undefined;
  }, [isExpanded, videoUrl]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.playbackRate = playbackRate;
  }, [playbackRate]);

  const controlsVisible = isExpanded || isTouchUi;

  const playerNode = (
    <div
      ref={containerRef}
      className={
        isExpanded
          ? "validation-player-fullscreen fixed inset-0 z-[99999] flex flex-col"
          : "relative w-full rounded-lg overflow-hidden group flex justify-center items-center"
      }
      style={isExpanded ? { width: "100vw", height: "100dvh", maxWidth: "100vw", maxHeight: "100dvh" } : undefined}
    >
      {isExpanded && <AppShellBackground className="z-0" />}
      <div className="validation-player-chrome relative z-[1] flex flex-col flex-1 min-h-0 w-full">
      {isExpanded && (
        <div className="validation-player-topbar flex items-center justify-between px-4 pb-2.5 pt-[max(10px,env(safe-area-inset-top,0px))] flex-shrink-0 glass-float app-topbar-glass bg-white/[0.008] backdrop-blur-md backdrop-saturate-[2.25] border-b border-white/[0.03]">
          <p className="text-sm font-bold text-white/90 truncate pr-3">{`${phaseLabel || "Validation"} \u00b7 Validation`}</p>
          <button
            type="button"
            onPointerDown={controlTap(exitExpanded)}
            className="validation-control-btn flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08] text-white text-xs font-semibold hover:bg-white/[0.10] active:bg-white/[0.14] transition touch-manipulation"
            aria-label="Close fullscreen"
          >
            <X className="w-4 h-4" />
            Close
          </button>
        </div>
      )}

      <div className={`${isExpanded ? "validation-player-stage-area flex-1 flex min-h-0 w-full p-2 pb-0" : "relative w-full"}`}>
        <div
          ref={stageRef}
          className={`validation-stage-frame relative overflow-hidden ${
            isExpanded ? "flex-1 w-full min-h-0 rounded-xl" : "w-full flex justify-center items-center rounded-lg"
          }`}
        >
          <AppShellBackground className="z-0 rounded-[inherit]" />
          <canvas ref={ambientCanvasRef} className="validation-ambient-canvas" aria-hidden="true" />
          <div ref={gutterLeftRef} className="validation-gutter-pane validation-gutter-fill" aria-hidden="true" />
          <div ref={gutterRightRef} className="validation-gutter-pane validation-metrics-gutter glass-float content-panel-glass rounded-2xl overflow-hidden">
            <div ref={panelDomRef} className="absolute inset-0 hidden flex flex-col p-3 gap-2 min-h-0 pointer-events-none">
              <div className="flex items-center justify-between flex-shrink-0 px-0.5">
                <span ref={panelPhaseRef} className="text-[13px] font-bold text-white leading-none">
                  {phaseLabel || "Trial"}
                </span>
                <span ref={panelNvpRef} className="text-[13px] font-bold leading-none" style={{ color: phaseColor.text }}>
                  NVP 0
                </span>
              </div>
              <div className="flex-1 flex flex-col gap-2 min-h-0">
                {panelRowDefs.map((row, i) => (
                  <div
                    key={row.id}
                    className="validation-metric-card flex-1 min-h-[28px] flex items-center justify-between px-3 py-1.5 rounded-xl bg-white/[0.05] border border-white/[0.04]"
                  >
                    <span className="text-[11px] font-semibold text-white/50 leading-tight">{row.label}</span>
                    <span
                      ref={(el) => {
                        panelMetricValueRefs.current[i] = el;
                      }}
                      className="text-[12px] font-bold text-white/90 tabular-nums"
                    />
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-2 flex-shrink-0">
                <div ref={chartHandWrapRef} className="validation-metric-card h-11 rounded-xl bg-white/[0.05] border border-white/[0.04] relative overflow-hidden">
                  <span className="absolute top-1.5 left-2.5 text-[10px] font-semibold text-white/50 z-[1] pointer-events-none">Hand speed</span>
                  <canvas ref={chartHandRef} className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true" />
                </div>
                <div ref={chartElbowWrapRef} className="validation-metric-card h-11 rounded-xl bg-white/[0.05] border border-white/[0.04] relative overflow-hidden">
                  <span className="absolute top-1.5 left-2.5 text-[10px] font-semibold text-white/50 z-[1] pointer-events-none">Elbow angle</span>
                  <canvas ref={chartElbowRef} className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true" />
                </div>
                <div ref={chartTrunkWrapRef} className="validation-metric-card h-11 rounded-xl bg-white/[0.05] border border-white/[0.04] relative overflow-hidden">
                  <span className="absolute top-1.5 left-2.5 text-[10px] font-semibold text-white/50 z-[1] pointer-events-none">Trunk X</span>
                  <canvas ref={chartTrunkRef} className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true" />
                </div>
              </div>
            </div>
          </div>
          <div ref={gutterTopRef} className="validation-gutter-pane validation-gutter-fill" aria-hidden="true" />
          <div ref={gutterBottomRef} className="validation-gutter-pane validation-gutter-fill" aria-hidden="true" />

          <div
            ref={contentWrapRef}
            className={`validation-content-fit validation-content-box relative shrink-0 max-w-full max-h-full overflow-hidden cursor-pointer ${
              isExpanded ? "z-[8]" : "z-[8] w-full flex items-center justify-center"
            }`}
            style={{ transform: "translateZ(0)", WebkitTransform: "translateZ(0)" }}
            onPointerUp={onVideoSurfacePointerUp}
            role="button"
            tabIndex={0}
            aria-label={isPlaying ? "Pause video" : "Play video"}
            onKeyDown={(e) => {
              if (e.key === " " || e.key === "Enter") {
                e.preventDefault();
                togglePlay();
              }
            }}
          >
              <video
                ref={videoRef}
                src={videoUrl}
                playsInline
                webkit-playsinline="true"
                muted
                preload="auto"
                className={`block object-contain bg-transparent w-full h-full pointer-events-none ${
                  isExpanded ? "" : "max-w-full max-h-[80vh]"
                }`}
                onError={(e) => onError?.(e?.target?.error || new Error("Video failed to load"))}
              />
              <canvas
                ref={canvasRef}
                className="absolute pointer-events-none"
                style={{ transform: "translateZ(0)", WebkitTransform: "translateZ(0)" }}
              />
              {sourceMismatch ? (
                <div
                  className="absolute pointer-events-none"
                  style={{ left: 0, right: 0, top: 0, padding: "8px" }}
                >
                  <p
                    style={{
                      margin: "0 auto",
                      maxWidth: "22rem",
                      borderRadius: "6px",
                      background: "rgba(0,0,0,0.7)",
                      padding: "4px 8px",
                      textAlign: "center",
                      fontSize: "11px",
                      lineHeight: 1.4,
                      color: "rgba(253,230,138,0.92)",
                    }}
                  >
                    {"Drawing paused \u2014 this clip is not the analyzed original. Reloading it\u2026"}
                  </p>
                </div>
              ) : null}
          </div>
        </div>
      </div>

      <canvas ref={recCanvasRef} className="hidden" />

      <div
        className={`validation-player-controls-wrap z-[30] ${
          isExpanded ? "relative flex-shrink-0 pointer-events-auto" : "absolute inset-x-0 bottom-0 pointer-events-none"
        } px-3 pt-2 pb-[max(12px,env(safe-area-inset-bottom,0px))] transition-opacity ${
          controlsVisible ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
      >
        <div className="validation-player-controls glass-float app-topbar-glass pointer-events-auto touch-manipulation">
          <div className="validation-controls-row validation-controls-transport">
            <button
              type="button"
              onPointerDown={controlTap(togglePlay)}
              className="validation-control-btn validation-control-icon"
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button
              type="button"
              onPointerDown={controlTap(() => stepFrame(-1))}
              className="validation-control-btn validation-control-icon"
              title="Previous frame"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onPointerDown={controlTap(() => stepFrame(1))}
              className="validation-control-btn validation-control-icon"
              title="Next frame"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <span className="validation-controls-time">
              {formatTime(displayTime)} / {formatTime(displayDuration)}
            </span>
          </div>

          <div className="validation-controls-row validation-controls-tools">
            <button
              type="button"
              onPointerDown={controlTap(() => setOverlayStyle((s) => (s === "chalk" ? "clinical" : "chalk")))}
              className={`validation-control-btn validation-control-chip ${
                overlayStyle === "chalk" ? "is-active" : ""
              }`}
              title={overlayStyle === "chalk" ? "Chalk limb ribbons (tap for clinical)" : "Clinical skeleton (tap for chalk)"}
            >
              {overlayStyle === "chalk" ? "Chalk" : "Clinic"}
            </button>
            <button
              type="button"
              onPointerDown={controlTap(toggleSpeed)}
              className="validation-control-btn validation-control-chip"
              title="Playback speed"
            >
              {playbackRate}x
            </button>
            <button
              type="button"
              onPointerDown={controlTap(requestFullscreen)}
              className="validation-control-btn validation-control-icon"
              title={isExpanded ? "Exit fullscreen" : "Fullscreen"}
            >
              {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </button>
            {recording ? (
              <button
                type="button"
                onPointerDown={controlTap(() => { stopRecording(); })}
                className="validation-control-btn validation-control-chip validation-control-record is-recording"
                title="Stop recording and save to patient Drive"
              >
                <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
                <span>Stop {Math.round(renderProgress)}%</span>
              </button>
            ) : (
              <button
                type="button"
                onPointerDown={controlTap(() => { void handleScreenRecord(); })}
                disabled={downloadBusy}
                className="validation-control-btn validation-control-chip validation-control-record"
                title="Screen-record this view and save to patient Drive"
              >
                <Circle className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
                <span>{downloadBusy ? "..." : "Record"}</span>
              </button>
            )}
          </div>

          <div
            className="validation-seek-bar"
            onPointerDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
              try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* ignore */ }
              handleSeek(e);
            }}
            onPointerMove={(e) => {
              if (!e.currentTarget.hasPointerCapture?.(e.pointerId)) return;
              e.preventDefault();
              handleSeek(e);
            }}
            title="Seek"
          >
            <div
              className="validation-seek-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
      </div>
    </div>
  );

  if (isExpanded && typeof document !== "undefined") {
    return (
      <>
        <div className="w-full min-h-[120px] rounded-lg bg-black/30 border border-white/10 flex items-center justify-center text-[11px] text-white/45">
          Fullscreen ? tap Close to return
        </div>
        {createPortal(playerNode, document.body)}
      </>
    );
  }

  return playerNode;
}

export default ValidationOverlayPlayer;
