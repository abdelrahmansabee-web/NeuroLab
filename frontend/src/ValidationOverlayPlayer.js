import React, { useRef, useState, useEffect, useLayoutEffect, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import { Play, Pause, Maximize, Minimize2, ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { downloadBlob } from "./downloadUtils";
import {
  buildTremorCameraTrack,
  formatTremorPower,
  resolveTremorMetrics,
} from "./tremorMetrics";
import {
  computeValidationPanelLive,
  elbowAngVelAt,
  pickOverlayMetric,
} from "./validationPanelMetrics";
import {
  buildPinchEvidenceLines,
  buildTremorEvidenceLines,
  drawEvidenceCard,
  drawTremorCameraEvidence,
  localTremorActivity,
  localTremorEnvelopeAt,
  pinchApertureFromFrame,
  pinchApertureWindowStats,
} from "./overlayMetricEvidence";
import { drawPanelKinematicMarks, drawTableSurfaceLine } from "./overlayPanelMarks";
import { detectCupFromRgba } from "./overlayCupTable";
import {
  clientPointToOverlayNorm,
  hitTableMark,
  loadTableUserMark,
  saveTableUserMark,
  tableMarkHitGeom,
} from "./overlayTableUserMark";
import { isAppleTouchVideo, shouldRestartPlayback } from "./overlayVideoPlayback";
import {
  overlayPortalStyle,
  overlaySlotAspect,
  overlaySlotReserveStyle,
  readSlotBox,
} from "./overlayExpandLayout";
import {
  drawClinicalSkeleton,
  drawChalkJoint,
  drawChalkStick,
  HAND_FINGER_ORDER,
  SKELETON_PALETTE,
} from "./clinicalSkeleton";

export { computeOverlayMetrics, computeValidationPanelLive } from "./validationPanelMetrics";

/** Same background treatment as App.js shell (bg.jpg + blur/dim). */
const APP_BG_URL = "/bg.jpg";
const APP_BG_FILTER = "blur(24px) brightness(0.55) saturate(0.80)";
const APP_BG_SCALE = "scale(1.08)";
const APP_BG_OVERLAY = "rgba(8, 8, 8, 0.18)";

function sampleCupFromVideo(video, palm) {
  if (!video || video.readyState < 2) return null;
  if (isAppleTouchVideo()) return null;
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) return null;
  try {
    const cw = Math.min(w, 360);
    const ch = Math.max(1, Math.round(h * (cw / w)));
    if (!sampleCupFromVideo._c) sampleCupFromVideo._c = document.createElement("canvas");
    const canvas = sampleCupFromVideo._c;
    canvas.width = cw;
    canvas.height = ch;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, cw, ch);
    const img = ctx.getImageData(0, 0, cw, ch);
    return detectCupFromRgba(img.data, cw, ch, { palm });
  } catch (_err) {
    return null;
  }
}

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
  // iPad/touch: cap at 1.0 — large canvases block the main thread and lag video + overlay.
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
  // Display buffer = CSS size × DPR (lighter while watching).
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

/** @deprecated use drawPanelCardRect — kept for inline fallback */
function drawLightGlassRect(ctx, x, y, w, h, radius, opts = {}) {
  drawPanelCardRect(ctx, x, y, w, h, radius, opts);
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

/** Letterbox gutters are transparent — app bg.jpg shows through (see index.css). */
function drawAmbientFromVideo() {
  return null;
}

function hideLetterboxGutters(gutters) {
  placeGutterChrome(gutters.left, { left: 0, top: 0, width: 0, height: 0 });
  placeGutterChrome(gutters.right, { left: 0, top: 0, width: 0, height: 0 });
  placeGutterChrome(gutters.top, { left: 0, top: 0, width: 0, height: 0 });
  placeGutterChrome(gutters.bottom, { left: 0, top: 0, width: 0, height: 0 });
}

/**
 * Compact card: contain the full frame in (card width × 80vh).
 * Do not letterbox a portrait clip into a collapsed landscape hole.
 */
function syncCompactVideoBox(video, stageEl, gutters, contentWrap) {
  const stageW = stageEl.clientWidth;
  const vw = video.videoWidth || 0;
  const vh = video.videoHeight || 0;
  if (stageW < 2 || !vw || !vh) {
    hideLetterboxGutters(gutters);
    return { externalPanel: false, rightGutter: 0 };
  }
  const viewH = window.visualViewport?.height || window.innerHeight || 0;
  const maxH = Math.max(120, viewH * 0.8);
  const scale = Math.min(stageW / vw, maxH / vh);
  const displayW = vw * scale;
  const displayH = vh * scale;
  if (contentWrap) {
    contentWrap.style.position = "relative";
    contentWrap.style.left = "";
    contentWrap.style.top = "";
    contentWrap.style.width = `${displayW}px`;
    contentWrap.style.height = `${displayH}px`;
    contentWrap.style.maxWidth = "100%";
    contentWrap.style.maxHeight = "80vh";
    contentWrap.style.flexShrink = "0";
    contentWrap.style.zIndex = "8";
  }
  video.style.width = "100%";
  video.style.height = "100%";
  video.style.objectFit = "contain";
  hideLetterboxGutters(gutters);
  return {
    externalPanel: false,
    rightGutter: 0,
    panelW: 0,
    panelH: displayH,
    stageW,
    stageH: displayH,
    leftG: 0,
    topG: 0,
    rightG: 0,
    bottomG: 0,
  };
}

/** Position letterbox gutters (does not touch overlay mapping). */
function syncLetterboxGutters(video, stageEl, gutters, contentWrap, absoluteVideoBox = false) {
  if (!video || !stageEl) return { externalPanel: false, rightGutter: 0 };

  if (!absoluteVideoBox) {
    return syncCompactVideoBox(video, stageEl, gutters, contentWrap);
  }

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
    contentWrap.style.position = "absolute";
    contentWrap.style.left = `${vidLeft}px`;
    contentWrap.style.top = `${vidTop}px`;
    contentWrap.style.width = `${displayW}px`;
    contentWrap.style.height = `${displayH}px`;
    contentWrap.style.flexShrink = "0";
    contentWrap.style.zIndex = "8";
  }
  video.style.width = "100%";
  video.style.height = "100%";
  video.style.objectFit = "contain";

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

/** Full LE / gait / core validation panel — all product variables. */
const LE_VALIDATION_PANEL_ROWS = [
  { id: "mov_time", label: "Movement time", kind: "metric", metricKeys: ["movement_time_sec", "sts_time_sec"], suffix: " s", decimals: 2 },
  { id: "mov_quality", label: "Quality index", kind: "metric", metricKeys: ["movement_quality_index"] },
  { id: "sparc_com", label: "SPARC (COM)", kind: "metric", metricKeys: ["sparc_com"], decimals: 2 },
  { id: "lr_sym", label: "L/R symmetry", kind: "metric", metricKeys: ["lr_symmetry_index"], decimals: 2 },
  { id: "gait_speed", label: "Gait speed", kind: "metric", metricKeys: ["gait_speed_m_s"], suffix: " m/s", decimals: 2 },
  { id: "cadence", label: "Cadence", kind: "metric", metricKeys: ["cadence_spm"], suffix: " /min", decimals: 0 },
  { id: "speed_pct", label: "Speed % of norm", kind: "metric", metricKeys: ["pct_of_norm_gait_speed_m_s"], suffix: "%", decimals: 0 },
  { id: "cadence_pct", label: "Cadence % of norm", kind: "metric", metricKeys: ["pct_of_norm_cadence_spm"], suffix: "%", decimals: 0 },
  { id: "df_l", label: "Ankle DF L", kind: "metric", metricKeys: ["ankle_df_peak_L_deg"], suffix: "°", decimals: 1 },
  { id: "df_r", label: "Ankle DF R", kind: "metric", metricKeys: ["ankle_df_peak_R_deg"], suffix: "°", decimals: 1 },
  { id: "pf_l", label: "Ankle PF L", kind: "metric", metricKeys: ["ankle_pf_peak_L_deg"], suffix: "°", decimals: 1 },
  { id: "pf_r", label: "Ankle PF R", kind: "metric", metricKeys: ["ankle_pf_peak_R_deg"], suffix: "°", decimals: 1 },
  { id: "df_pct", label: "DF L % of norm", kind: "metric", metricKeys: ["pct_of_norm_ankle_df_peak_L_deg"], suffix: "%", decimals: 0 },
  { id: "pf_pct", label: "PF L % of norm", kind: "metric", metricKeys: ["pct_of_norm_ankle_pf_peak_L_deg"], suffix: "%", decimals: 0 },
  { id: "ankle_rom_l", label: "Ankle ROM L", kind: "metric", metricKeys: ["ankle_sagittal_rom_L_deg"], suffix: "°", decimals: 1 },
  { id: "ankle_rom_r", label: "Ankle ROM R", kind: "metric", metricKeys: ["ankle_sagittal_rom_R_deg"], suffix: "°", decimals: 1 },
  { id: "fpa_l", label: "Foot progression L", kind: "metric", metricKeys: ["foot_progression_angle_L_deg"], suffix: "°", decimals: 1 },
  { id: "fpa_r", label: "Foot progression R", kind: "metric", metricKeys: ["foot_progression_angle_R_deg"], suffix: "°", decimals: 1 },
  { id: "hip_rot_l", label: "Hip rot ROM L", kind: "metric", metricKeys: ["hip_rotation_rom_L_deg"], suffix: "°", decimals: 1 },
  { id: "hip_rot_r", label: "Hip rot ROM R", kind: "metric", metricKeys: ["hip_rotation_rom_R_deg"], suffix: "°", decimals: 1 },
  { id: "knee_sw_l", label: "Swing knee flex L", kind: "metric", metricKeys: ["knee_flex_peak_swing_L_deg"], suffix: "°", decimals: 1 },
  { id: "knee_sw_r", label: "Swing knee flex R", kind: "metric", metricKeys: ["knee_flex_peak_swing_R_deg"], suffix: "°", decimals: 1 },
  { id: "hip_rom_l", label: "Hip ROM L", kind: "metric", metricKeys: ["hip_rom_L_deg"], suffix: "°", decimals: 1 },
  { id: "hip_rom_r", label: "Hip ROM R", kind: "metric", metricKeys: ["hip_rom_R_deg"], suffix: "°", decimals: 1 },
  { id: "knee_rom_l", label: "Knee ROM L", kind: "metric", metricKeys: ["knee_rom_L_deg"], suffix: "°", decimals: 1 },
  { id: "knee_rom_r", label: "Knee ROM R", kind: "metric", metricKeys: ["knee_rom_R_deg"], suffix: "°", decimals: 1 },
  { id: "pelvis_rot", label: "Pelvis rotation ROM", kind: "metric", metricKeys: ["pelvis_rotation_rom_deg"], suffix: "°", decimals: 1 },
  { id: "trunk_lean", label: "Trunk lean max", kind: "metric", metricKeys: ["trunk_lean_max_deg"], suffix: "°", decimals: 1 },
  { id: "trunk_flex", label: "Trunk flexion ROM", kind: "metric", metricKeys: ["trunk_flexion_rom_deg"], suffix: "°", decimals: 1 },
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
  { id: "min_knee", label: "Min knee (squat)", kind: "metric", metricKeys: ["min_knee_angle_deg"], suffix: "°", decimals: 1 },
  { id: "sway_path", label: "COM sway path", kind: "metric", metricKeys: ["com_sway_path_norm"], decimals: 2 },
  { id: "sway_area", label: "COM sway area", kind: "metric", metricKeys: ["com_sway_area_norm"], decimals: 2 },
  { id: "sway_vel", label: "Sway velocity", kind: "metric", metricKeys: ["sway_velocity_mean"], decimals: 1 },
  { id: "load_sym", label: "Loading symmetry", kind: "metric", metricKeys: ["lr_loading_symmetry"], decimals: 2 },
];

function getValidationPanelRowDefs(overlayData, clinicalTask) {
  if (isLeClinicalTask(clinicalTask, overlayData)) {
    return LE_VALIDATION_PANEL_ROWS;
  }
  // UE study / kinematics table variables (live + metrics) — full panel, not 2-row stub.
  return UE_VALIDATION_PANEL_ROWS;
}

/** Upper-extremity validation panel — matches kinematics table core + validation extras. */
const UE_VALIDATION_PANEL_ROWS = [
  { id: "mov_time", label: "Movement time", kind: "live", key: "movementTime", suffix: " s", decimals: 2 },
  { id: "mov_quality", label: "Movement quality", kind: "metric", metricKeys: ["movement_quality_index"], accent: true },
  { id: "straightness", label: "Straightness", kind: "live", key: "straightness", decimals: 2 },
  { id: "peak_vel", label: "Peak velocity", kind: "peakVelCm", accent: true },
  { id: "pause", label: "Pause / stops", kind: "pause" },
  { id: "trunk", label: "Trunk ratio", kind: "live", key: "trunkRatio", decimals: 2 },
  { id: "sh_elev", label: "Shoulder elevation", kind: "shoulderElev" },
  { id: "elbow_mean", label: "Elbow angle mean", kind: "metric", metricKeys: ["elbow_angle_mean_deg", "elbow_angle_mean"], suffix: "°", decimals: 1 },
  { id: "tremor", label: "Tremor 8–12 Hz", kind: "tremor", tremorKey: "tremor_8_12hz_power" },
  { id: "tremor_hz", label: "Tremor peak freq", kind: "tremorFreq", tremorKey: "tremor_peak_freq_hz" },
  { id: "kin_abd", label: "Shoulder abduction", kind: "live", key: "shoulderAbduction", suffix: "°", decimals: 0 },
  { id: "kin_finger", label: "Finger quality", kind: "live", key: "fingerQuality", decimals: 0 },
];

function formatPanelRowValue(row, live, overlayData, formatValue) {
  if (row.kind === "live") {
    const v = live[row.key];
    if (v == null || Number.isNaN(v)) return "—";
    if (row.id !== "kin_abd" && row.id !== "kin_finger" && v <= 0) return "—";
    if ((row.id === "kin_abd" || row.id === "kin_finger") && v <= 0) return "—";
    return `${formatValue(v, row.decimals ?? 2)}${row.suffix || ""}`;
  }
  if (row.kind === "peakVelCm") {
    const cm = pickOverlayMetric(overlayData, ["peak_velocity_cm_s"]);
    if (cm != null && Number(cm) > 0) return `${formatValue(Number(cm), 1)} cm/s`;
    const v = live.peakElbowAngVel;
    if (v == null || Number.isNaN(v) || v <= 0) return "—";
    return `${formatValue(v, 0)} °/s`;
  }
  if (row.kind === "pause") {
    const { pauseTime, stops } = live;
    if (pauseTime > 0 || stops > 0) return `${formatValue(pauseTime, 2)} s / ${stops}`;
    return "—";
  }
  if (row.kind === "shoulderElev") {
    const cm = pickOverlayMetric(overlayData, ["shoulder_elevation_cm"]);
    if (cm != null && Number(cm) > 0) return `${formatValue(Number(cm), 1)} cm`;
    const v = live.shoulderElevationPalm || live.shoulderElevationTable || live.shoulderElevation;
    if (v > 0) return formatValue(v, 3);
    return "—";
  }
  if (row.kind === "tremor") {
    const v = live[row.tremorKey];
    return formatTremorPower(v);
  }
  if (row.kind === "tremorIndex") {
    const v = live[row.tremorKey];
    if (v == null || Number.isNaN(v)) return "—";
    return Math.round(Number(v)).toString();
  }
  if (row.kind === "tremorFreq") {
    const v = live[row.tremorKey] ?? pickOverlayMetric(overlayData, [row.tremorKey]);
    if (v == null || Number.isNaN(Number(v))) return "—";
    return `${Number(v).toFixed(1)} Hz`;
  }
  if (row.kind === "metric" && row.metricKeys) {
    const v = pickOverlayMetric(overlayData, row.metricKeys);
    if (v == null) return "—";
    const decimals = row.decimals != null ? row.decimals : 2;
    const formatted = formatValue(v, decimals);
    return row.suffix ? `${formatted}${row.suffix}` : formatted;
  }
  return "—";
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
  const recordingRef = useRef(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [displayTime, setDisplayTime] = useState(0);
  const [displayDuration, setDisplayDuration] = useState(0);
  const [recording, setRecording] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadBusy, setDownloadBusy] = useState(false);
  /** clinical = bone sticks; chalk = soft chalk limb ribbons (default) */
  const [overlayStyle, setOverlayStyle] = useState("chalk");
  /** NVP / straightness / trunk / shoulder / pause marks on the drawing (not the right panel). */
  const [showKinematicMarks, setShowKinematicMarks] = useState(true);
  const [renderProgress, setRenderProgress] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [videoAspect, setVideoAspect] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isTouchUi, setIsTouchUi] = useState(false);
  const slotRef = useRef(null);
  const [slotBox, setSlotBox] = useState(null);
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
  const usePresentedTimeRef = useRef(false);
  const lastPanelUpdateIdxRef = useRef(-1);
  const liveMetricsCacheRef = useRef(null);
  const tremorLiveCacheRef = useRef({ idx: -1, data: null });
  const progressRafRef = useRef(0);
  const paintPendingRef = useRef(false);
  /** Keep last good finger dots briefly so they don't vanish on 1–2 missing frames. */
  const fingerStickyRef = useRef({});
  /** Last live finger canvas points (no EMA). Used only to reset on seeks. */
  const fingerSmoothRef = useRef({});
  const cupLiveRef = useRef(null);
  const cupTriesRef = useRef(0);
  const tableUserRef = useRef(null);
  const tableGeomRef = useRef(null);
  const tableDragRef = useRef({ active: false, moved: false, pointerId: null, start: null });
  const tablePlaceModeRef = useRef(false);
  const skipPlayToggleRef = useRef(false);
  const overlayDataRef = useRef(overlayData);
  overlayDataRef.current = overlayData;
  const videoUrlRef = useRef(videoUrl);
  videoUrlRef.current = videoUrl;
  const [tableUserMark, setTableUserMark] = useState(null);
  const [tablePlaceMode, setTablePlaceMode] = useState(false);
  const [tableDragging, setTableDragging] = useState(false);

  const phaseColor = useMemo(() => {
    const p = (phaseLabel || "").toLowerCase();
    if (p.includes("post")) return { main: "#10b981", glow: "rgba(16,185,129,0.45)", text: "#6ee7b7" };
    if (p.includes("pre")) return { main: "#0ea5e9", glow: "rgba(14,165,233,0.45)", text: "#7dd3fc" };
    return { main: "#f59e0b", glow: "rgba(245,158,11,0.45)", text: "#fcd34d" };
  }, [phaseLabel]);

  const panelRowDefs = useMemo(() => getValidationPanelRowDefs(overlayData, clinicalTask), [overlayData, clinicalTask]);

  const frames = overlayData?.frames || [];
  const fps = overlayData?.fps || 60;
  const metrics = overlayData?.metrics || {};
  const win = overlayData?.movement_window || { start_idx: 0, end_idx: frames.length - 1 };
  const velocityProfile = overlayData?.velocity_profile;
  const peakFrames = overlayData?.peak_frames || [];
  const tremorCameraTrack = useMemo(() => buildTremorCameraTrack(overlayData), [overlayData]);

  const getElbowAngVel = useCallback((idx) => elbowAngVelAt(frames, fps, idx), [frames, fps]);

  const peakElbowAngVel = useMemo(() => {
    let maxV = 0;
    for (let i = 1; i < frames.length; i++) {
      const v = getElbowAngVel(i);
      if (v > maxV) maxV = v;
    }
    return maxV;
  }, [frames, getElbowAngVel]);
  const peakV = peakElbowAngVel || 1;

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
    if (v == null || Number.isNaN(v)) return "—";
    if (digits === 0) return Math.round(v).toString();
    return Number(v).toFixed(digits);
  };

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const stageEl = stageRef.current;
    const contentEl = contentWrapRef.current;
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

    const synced = syncOverlayCanvas(
      video,
      canvas,
      overlayData,
      canvasLayoutCacheRef.current,
      contentEl,
      { nativeBuffer: recordingRef.current },
    );
    if (!synced) return;
    const { cw, ch } = synced;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, cw, ch);

    if (stageEl && ambientCanvasRef.current) {
      drawAmbientFromVideo(video, stageEl, ambientCanvasRef.current, gutterLayout, {
        left: gutterLeftRef.current,
        top: gutterTopRef.current,
        bottom: gutterBottomRef.current,
      });
    }
    const useExternalPanel = Boolean(gutterLayout.externalPanel);
    const panelCtx = ctx;
    if (panelDomRef.current) {
      panelDomRef.current.classList.toggle("hidden", !useExternalPanel);
    }

    if (!frames.length) return;

    const touchPerf = isCoarsePointerDevice();
    const shadowOff = touchPerf ? 0 : undefined;

    // RVFC paints pass the presented-frame mediaTime; other paints use currentTime.
    const playbackTime = usePresentedTimeRef.current
      ? videoTimeRef.current
      : (video.currentTime ?? 0);
    const { idx, alpha } = getFrameState(playbackTime);
    const updatePanelMetrics = !touchPerf || video.paused || idx % 8 === 0 || idx >= win.end_idx;
    const updatePanelCharts = !touchPerf || video.paused;
    const f = frames[idx];
    const fNext = frames[Math.min(idx + 1, frames.length - 1)];
    if (!f) return;

    const color = phaseColor;

    function pt(name) {
      const p = f[name];
      const pn = alpha > 0 ? fNext?.[name] : null;
      if (!p || p[0] == null || p[1] == null) return null;
      let nx = p[0];
      let ny = p[1];
      if (pn && pn[0] != null && pn[1] != null && alpha > 0) {
        nx = p[0] + (pn[0] - p[0]) * alpha;
        ny = p[1] + (pn[1] - p[1]) * alpha;
      }
      const isHandLm = /^(index|thumb|pinky|middle|ring|hl_wrist)$/.test(name);
      if (isHandLm && (nx <= 0.0002 || nx >= 0.9998 || ny <= 0.0002 || ny >= 0.9998)) return null;
      return [nx * cw, ny * ch];
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

    if (
      !isAppleTouchVideo()
      && !overlayData?.cup
      && !tableUserRef.current
      && !cupLiveRef.current
      && cupTriesRef.current < 8
      && video.readyState >= 2
    ) {
      const restI = Number.isFinite(Number(win?.start_idx)) ? Number(win.start_idx) : 0;
      const restPalm = frames[restI]?.palm || overlayData?.start_palm;
      cupTriesRef.current += 1;
      const found = sampleCupFromVideo(video, restPalm);
      if (found) cupLiveRef.current = found;
    }

    const overlayForTable = tableUserRef.current
      ? { ...overlayData, table_user: tableUserRef.current }
      : overlayData;
    const tableGeom = drawTableSurfaceLine(ctx, overlayForTable, {
      shoulder,
      frames,
      idx,
      startIdx: win.start_idx,
      cw,
      ch,
      shoulderWidthPx: Number(overlayData?.shoulder_width_px) || 0,
      noShadow: Boolean(touchPerf),
      cup: overlayData?.cup || cupLiveRef.current,
      userMark: tableUserRef.current,
      placing: tablePlaceModeRef.current,
    });
    tableGeomRef.current = tableMarkHitGeom(tableGeom, cw);

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

    const currentNVP = peakFrames.filter((pi) => pi <= idx).length;

    let panelLive = liveMetricsCacheRef.current?.panelLive;
    if (updatePanelMetrics) {
      panelLive = computeValidationPanelLive(overlayData, idx);
      liveMetricsCacheRef.current = {
        ...(liveMetricsCacheRef.current || {}),
        idx,
        panelLive,
        currentPeakElbowAngVel: panelLive?.peakElbowAngVel ?? 0,
        currentMovementTime: panelLive?.movementTime ?? 0,
        currentPauseTime: panelLive?.pauseTime ?? 0,
        currentStops: panelLive?.stops ?? 0,
        currentStraightness: panelLive?.straightness ?? 0,
        currentTrunkRatio: panelLive?.trunkRatio ?? 0,
        fingerQuality: panelLive?.fingerQuality ?? 0,
      };
      tremorLiveCacheRef.current = {
        idx,
        data: {
          tremor_8_12hz_power: panelLive?.tremor_8_12hz_power,
          tremor_index: panelLive?.tremor_index,
          tremor_peak_freq_hz: panelLive?.tremor_peak_freq_hz,
        },
        adlData: {
          tremor_8_12hz_power: panelLive?.adl_tremor_8_12hz_power,
        },
      };
      lastPanelUpdateIdxRef.current = idx;
    }
    const cachedLive = liveMetricsCacheRef.current || {};
    const currentPeakElbowAngVel = panelLive?.peakElbowAngVel ?? cachedLive.currentPeakElbowAngVel ?? 0;
    const currentMovementTime = panelLive?.movementTime ?? cachedLive.currentMovementTime ?? 0;
    const currentPauseTime = panelLive?.pauseTime ?? cachedLive.currentPauseTime ?? 0;
    const currentStops = panelLive?.stops ?? cachedLive.currentStops ?? 0;
    const currentStraightness = panelLive?.straightness ?? cachedLive.currentStraightness ?? 0;
    const currentTrunkRatio = panelLive?.trunkRatio ?? cachedLive.currentTrunkRatio ?? 0;

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
    let currentFingerQuality = panelLive?.fingerQuality ?? cachedLive.fingerQuality ?? 0;
    let tremorLive = tremorLiveCacheRef.current?.data;
    let adlTremorLive = tremorLiveCacheRef.current?.adlData;
    const resolvedTremor = resolveTremorMetrics(overlayData);

    const showExtendedKin = false; // UE abduction/finger overlays disabled

    const dpr = overlayCanvasDpr();
    const labelSize = `${Math.round(10 * dpr)}px`;
    const labelPad = 5 * dpr;
    const labelH = Math.round(12 * dpr);

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
    if (!touchPerf) {
      if (shoulder && showExtendedKin && currentShoulderAbduction > 0) {
        drawSimpleLabel(`Abd ${currentShoulderAbduction.toFixed(0)}°`, shoulder, shoulder[0] > cx ? -118 : 14, 6, {
          color: "#93c5fd",
          border: "rgba(59,130,246,0.55)",
        });
      }
      if (elbow) {
        drawSimpleLabel(`El ${currentElbowAngle.toFixed(0)}°`, elbow, elbow[0] > cx ? -80 : 14, -22, { color: color.text, border: color.glow });
      }
      if (palm) {
        drawSimpleLabel(`Ha ${Math.round(speed)} °/s`, palm, palm[0] > cx ? -100 : 18, -24, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
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
      if (!pair || pair[0] == null || pair[1] == null) return null;
      let nx = pair[0];
      let ny = pair[1];
      if (pairNext && pairNext[0] != null && pairNext[1] != null && alpha > 0) {
        nx = pair[0] + (pairNext[0] - pair[0]) * alpha;
        ny = pair[1] + (pairNext[1] - pair[1]) * alpha;
      }
      return [nx * cw, ny * ch];
    }

    // Pre-v37 overlays re-anchored HL tips onto pose wrist (floated off fingers).
    // Undo: tip' = tip - poseWrist + hlWrist. v37+ already stores absolute HL.
    const overlayVer = Number(overlayData?.overlay_version) || 0;
    const needUndoReanchor = overlayVer < 37;
    const poseWristPt = pt("wrist");
    const hlWristPt = pt("hl_wrist");
    const undoReanchor = (cpt) => {
      if (!needUndoReanchor || !cpt || !poseWristPt || !hlWristPt) return cpt;
      return [
        cpt[0] - poseWristPt[0] + hlWristPt[0],
        cpt[1] - poseWristPt[1] + hlWristPt[1],
      ];
    };

    const smoothStore = fingerSmoothRef.current;
    const smoothFinger = (key, cpt, live) => {
      if (!cpt) return null;
      if (!live) return cpt;
      if (smoothStore._idx != null && Math.abs(idx - smoothStore._idx) > 8) {
        Object.keys(smoothStore).forEach((k) => { if (k !== "_idx") delete smoothStore[k]; });
      }
      smoothStore._idx = idx;
      smoothStore[key] = [...cpt];
      return cpt;
    };

    const jointDots = [];
    // Hold last-good finger dots across ~0.4s of video frames (not paint FPS).
    const stickyHoldFrames = Math.max(10, Math.round(fps * 0.4));
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

    if (fingerJoints) {
      HAND_FINGER_ORDER.forEach((fid) => {
        const fj = fingerJoints[fid];
        if (!fj) return;
        JOINT_ORDER.forEach((jname) => {
          const fjNext = fNext?.finger_joints?.[fid];
          let cpt = jointToCanvas(fj[jname], fjNext?.[jname]);
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
    } else {
      HAND_FINGER_ORDER.forEach((id) => {
        let tipPt = undoReanchor(pt(id));
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
              blur: touchPerf ? 0 : 3,
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

      if (!touchPerf && useHandHl) {
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
      if (!touchPerf && showExtendedKin && indexTip && currentFingerQuality > 0) {
        drawSimpleLabel(`Fi ${currentFingerQuality}`, indexTip, indexTip[0] > cx ? -68 : 14, 16, {
          color: "#ddd6fe",
          border: "rgba(167,139,250,0.6)",
        });
      }
    }

    if (showKinematicMarks && !isLeClinicalTask(clinicalTask, overlayData)) {
      drawPanelKinematicMarks(ctx, {
        overlayData: overlayForTable,
        frames,
        idx,
        cw,
        ch,
        palm,
        trunk,
        shoulder,
        peakFrames,
        noShadow: Boolean(touchPerf),
      });
    }

    // --- Tremor: backup pulsing halo on the hand + 8–12 Hz camera sparkline ---
    const tremorAnchor = palm || pt("wrist") || pt("hl_wrist");
    const swPxTremor = Number(overlayData?.shoulder_width_px) || 0;
    const tremorEnv = tremorAnchor ? localTremorEnvelopeAt(overlayData, idx) : null;
    const tremorAct = tremorAnchor ? localTremorActivity(frames, idx, fps, swPxTremor) : null;
    const tremorIntensity = tremorEnv != null ? Math.min(1, tremorEnv * 4) : tremorAct != null ? Math.min(1, tremorAct * 12) : 0;
    const tremorLivePow =
      idx >= win.end_idx
        ? resolvedTremor?.tremor_8_12hz_power
        : tremorLive?.tremor_8_12hz_power ?? resolvedTremor?.tremor_8_12hz_power;
    const tremorPeakHz =
      idx >= win.end_idx
        ? resolvedTremor?.tremor_peak_freq_hz
        : tremorLive?.tremor_peak_freq_hz ?? resolvedTremor?.tremor_peak_freq_hz;

    if (tremorAnchor && idx >= win.start_idx && idx <= win.end_idx && tremorCameraTrack) {
      drawTremorCameraEvidence(ctx, {
        anchor: tremorAnchor,
        idx,
        track: tremorCameraTrack,
        cw,
        ch,
        dpr,
        livePow: tremorLivePow,
        peakHz: tremorPeakHz,
        intensity: tremorIntensity,
      });
    }

    // --- Pinch aperture on skeleton (explains grasp quality) ---
    if (!touchPerf) {
      const fwPx = Number(overlayData?.frame_width_px) || cw;
      const fhPx = Number(overlayData?.frame_height_px) || ch;
      const swPx = swPxTremor;

      // Tremor halo from backup (REFERENCE_SNAPSHOT / v32.52): pulsing ring on the palm.
      if (tremorAnchor && idx >= win.start_idx && idx <= win.end_idx) {
        if (tremorIntensity > 0.02 || tremorLivePow != null) {
          const r = 14 + tremorIntensity * 42;
          const alphaHalo = 0.12 + tremorIntensity * 0.55;
          ctx.save();
          ctx.beginPath();
          ctx.arc(tremorAnchor[0], tremorAnchor[1], r, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(251,113,133,${Math.min(0.95, alphaHalo).toFixed(2)})`;
          ctx.lineWidth = 2.5 + tremorIntensity * 3;
          ctx.shadowColor = "rgba(251,113,133,0.65)";
          ctx.shadowBlur = 12 + tremorIntensity * 18;
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(tremorAnchor[0], tremorAnchor[1], Math.max(6, r * 0.45), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(251,113,133,${(0.08 + tremorIntensity * 0.28).toFixed(2)})`;
          ctx.fill();
          ctx.restore();
          drawSimpleLabel(
            `Tr ${formatTremorPower(tremorLivePow)}${tremorPeakHz != null ? ` · ${Number(tremorPeakHz).toFixed(1)}Hz` : ""}`,
            tremorAnchor,
            tremorAnchor[0] > cx ? -150 : 20,
            -52,
            { color: "#fda4af", border: "rgba(251,113,133,0.55)", bg: "rgba(40,10,18,0.85)" },
          );
          if (showExtendedKin || tremorLivePow != null) {
            drawEvidenceCard(
              ctx,
              buildTremorEvidenceLines(overlayData, tremorLivePow, tremorPeakHz),
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

      const thumbTip = jointDots.find((d) => d.fid === "thumb" && d.jname === "tip")?.cpt || pt("thumb");
      const indexTipEv = jointDots.find((d) => d.fid === "index" && d.jname === "tip")?.cpt || pt("index");
      if (thumbTip && indexTipEv) {
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

        // Ghost max / min aperture from window extrema frames
        if (winStats?.maxFrame != null && winStats?.minFrame != null) {
          const drawGhost = (fi, stroke) => {
            const gf = frames[fi];
            if (!gf?.index || !gf?.thumb) return;
            const a = toCanvas(gf.thumb);
            const b = toCanvas(gf.index);
            if (!a || !b) return;
            ctx.save();
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = stroke;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
            ctx.stroke();
            ctx.restore();
          };
          drawGhost(winStats.maxFrame, "rgba(167,139,250,0.35)");
          drawGhost(winStats.minFrame, "rgba(167,139,250,0.22)");
        }

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

    if (idx >= win.start_idx && idx <= win.end_idx && !touchPerf) {
      ctx.save();
      ctx.strokeStyle = color.glow;
      ctx.lineWidth = 3;
      ctx.shadowColor = color.main;
      ctx.shadowBlur = 10;
      ctx.strokeRect(5, 5, cw - 10, ch - 10);
      ctx.restore();
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
        tremor_8_12hz_power: panelLive?.tremor_8_12hz_power
          ?? tremorLive?.tremor_8_12hz_power
          ?? resolvedTremor?.tremor_8_12hz_power,
        tremor_index: panelLive?.tremor_index
          ?? tremorLive?.tremor_index
          ?? resolvedTremor?.tremor_index,
        index_tremor_8_12hz_power: panelLive?.index_tremor_8_12hz_power
          ?? resolvedTremor?.index_tremor_8_12hz_power,
        tremor_peak_freq_hz: panelLive?.tremor_peak_freq_hz
          ?? tremorLive?.tremor_peak_freq_hz
          ?? resolvedTremor?.tremor_peak_freq_hz,
        movement_quality_index: panelLive?.movement_quality_index
          ?? overlayData?.metrics?.movement_quality_index
          ?? pickOverlayMetric(overlayData, ["movement_quality_index"]),
        adl_tremor_8_12hz_power: panelLive?.adl_tremor_8_12hz_power
          ?? adlTremorLive?.tremor_8_12hz_power
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
    } else if (!touchPerf) {
    // Inline fallback panel (drawn on video canvas when gutter is narrow — skipped on iPad for performance)
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
    ctx.fillText(`Speed ${Math.round(speed)} °/s`, gx, gy - 4);
    }

  }, [frames, fps, win, peakV, velocityProfile, phaseColor, phaseLabel, getFrameIndex, getFrameState, peakFrames, tremorCameraTrack, getElbowAngVel, overlayData?.elbow_angle_profile, overlayData?.trunk_x_profile, overlayData?.table_surface_y, overlayData?.shoulder_palm_anchor, overlayData, clinicalTask, isExpanded, overlayStyle, showKinematicMarks]);

  const drawRecordingFrame = useCallback(() => {
    const video = videoRef.current;
    const recCanvas = recCanvasRef.current;
    const visCanvas = canvasRef.current;
    if (!video || !recCanvas || !visCanvas) return;
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    if (recCanvas.width !== vw || recCanvas.height !== vh) {
      recCanvas.width = vw;
      recCanvas.height = vh;
    }
    const ctx = recCanvas.getContext("2d", { alpha: false, desynchronized: true });
    if (!ctx) return;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    // Full-resolution source frame (not the CSS-scaled element bitmap).
    ctx.drawImage(video, 0, 0, vw, vh);
    // Overlay is already native-sized while recordingRef is true.
    ctx.drawImage(visCanvas, 0, 0, vw, vh);
  }, []);

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
    const pixels = Math.max(1, vw * vh);
    const captureFps = Math.min(60, Math.max(24, Math.round(Number(fps) || 30)));
    let sourceBytes = 0;
    try {
      if (videoUrl) {
        const res = await fetch(videoUrl);
        if (res.ok) {
          const blob = await res.blob();
          sourceBytes = blob.size || 0;
        }
      }
    } catch {
      /* ignore — fall back to pixel estimate */
    }
    const duration = Math.max(0.5, Number(video.duration) || 1);
    // Match or exceed source bitrate so re-encode does not visibly soften detail.
    let bps;
    if (sourceBytes > 1000) {
      bps = Math.round((sourceBytes * 8) / duration * 1.5);
    } else {
      // ~0.2 bits/pixel/frame ≈ high clinical quality for H.264/VP9 family
      bps = Math.round(pixels * captureFps * 0.2);
    }
    return {
      videoBitsPerSecond: Math.min(120_000_000, Math.max(40_000_000, bps)),
      captureFps,
    };
  }, [fps, videoUrl]);

  const startRecording = useCallback(async () => {
    const video = videoRef.current;
    const recCanvas = recCanvasRef.current;
    if (!video || !recCanvas) return;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") return;
    recordingRef.current = true;
    canvasLayoutCacheRef.current = { key: "", result: null };
    // Paint one native-res frame before capture so the first recorded frame is not blank.
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
      canvasLayoutCacheRef.current = { key: "", result: null };
      const blob = new Blob(recordedChunksRef.current, { type: mimeType.includes("mp4") ? "video/mp4" : "video/webm" });
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      onDownloadReady?.(url, blob);
      setRecording(false);
      // Restore display-sized overlay buffer after bake.
      requestAnimationFrame(() => {
        drawOverlay();
      });
      if (pendingDownloadRef.current) {
        pendingDownloadRef.current = false;
        const ext = (blob.type || "").includes("mp4") ? "mp4" : "webm";
        downloadBlob(blob, `${phaseLabel || "validation"}_overlay.${ext}`).catch((err) => {
          onError?.(err?.message || "Download failed");
        });
      }
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
      onError?.(err?.message || "Could not start high-quality bake");
    }
  }, [drawOverlay, drawRecordingFrame, estimateBakeBitrate, onDownloadReady, onError, phaseLabel]);

  const handleDownload = useCallback(async () => {
    if (recording || downloadBusy) return;
    setDownloadBusy(true);
    try {
      if (onRequestServerExport) {
        await onRequestServerExport();
        return;
      }
      if (downloadUrl) {
        const res = await fetch(downloadUrl);
        if (!res.ok) throw new Error(`Download failed (${res.status})`);
        const blob = await res.blob();
        const ext = (blob.type || "").includes("mp4") ? "mp4" : "webm";
        await downloadBlob(blob, `${phaseLabel || "validation"}_overlay.${ext}`);
        onDownloadReady?.(downloadUrl, blob);
        return;
      }
      if (serverExportFilename) {
        onError?.("Validation video not cached — tap Download again after it loads");
        return;
      }
      pendingDownloadRef.current = true;
      await startRecording();
    } catch (err) {
      pendingDownloadRef.current = false;
      onError?.(err?.message || "Download failed");
    } finally {
      setDownloadBusy(false);
    }
  }, [
    recording,
    downloadBusy,
    onRequestServerExport,
    downloadUrl,
    serverExportFilename,
    phaseLabel,
    startRecording,
    onDownloadReady,
    onError,
  ]);

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

    const runPaint = (explicitTime) => {
      if (Number.isFinite(explicitTime)) {
        videoTimeRef.current = explicitTime;
        usePresentedTimeRef.current = true;
      } else {
        videoTimeRef.current = video.currentTime ?? 0;
        usePresentedTimeRef.current = false;
      }
      lastPaintMediaTimeRef.current = videoTimeRef.current;
      drawOverlay();
      usePresentedTimeRef.current = false;
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
      const t = metadata?.mediaTime ?? video.currentTime ?? 0;
      runPaint(t);
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
      videoTimeRef.current = video.currentTime ?? 0;
      lastPaintMediaTimeRef.current = -1;
      setDisplayDuration(video.duration || 0);
      setDisplayTime(video.currentTime || 0);
      schedulePaint();
      tryAutoRender();
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
      const dur = Number(video.duration);
      if (Number.isFinite(dur) && dur > 0.08) {
        try {
          video.currentTime = Math.max(0, dur - 0.05);
        } catch (_err) {
          /* ignore */
        }
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
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("ended", onVideoEnded);
    window.addEventListener("resize", onResize);

    if (!video.paused) onPlay();
    else schedulePaint();

    return () => {
      video.removeEventListener("loadedmetadata", onLoadedMetadata);
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("ended", onVideoEnded);
      window.removeEventListener("resize", onResize);
      stopVfc();
      stopRafLoop();
      if (progressRafRef.current) cancelAnimationFrame(progressRafRef.current);
    };
  }, [videoUrl, drawOverlay, drawRecordingFrame, recording, onEnded, tryAutoRender]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !autoPlay) return;
    video.muted = true;
    video.play().catch(() => {});
  }, [videoUrl, autoPlay]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused || video.ended) {
      if (shouldRestartPlayback({
        ended: video.ended,
        currentTime: video.currentTime,
        duration: video.duration,
      })) {
        video.currentTime = 0;
      }
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  };

  const controlTap = (handler) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    handler(e);
  };

  const paintTableOverlay = () => {
    lastPaintMediaTimeRef.current = -1;
    drawOverlay();
  };

  const onTableChip = () => {
    if (tablePlaceModeRef.current) {
      setTablePlaceMode(false);
      tablePlaceModeRef.current = false;
      skipPlayToggleRef.current = true;
      paintTableOverlay();
      return;
    }
    const video = videoRef.current;
    if (video && !video.paused) video.pause();
    setTablePlaceMode(true);
    tablePlaceModeRef.current = true;
    skipPlayToggleRef.current = true;
    paintTableOverlay();
  };

  const onTablePointerDown = (e) => {
    if (e.button != null && e.button !== 0) return;
    const t = e.target;
    if (t instanceof Element && t.closest(".validation-player-controls, .validation-control-btn, .validation-seek-bar, .validation-player-topbar")) {
      return;
    }
    const canvas = canvasRef.current;
    const rect = canvas?.getBoundingClientRect?.();
    const placing = tablePlaceModeRef.current;
    const normHit = clientPointToOverlayNorm(e.clientX, e.clientY, rect);
    const cssW = rect?.width || 0;
    const cssH = rect?.height || 0;
    const hit = hitTableMark(normHit, tableGeomRef.current, {
      cssW,
      cssH,
      coarse: isCoarsePointerDevice(),
    });
    if (!placing && !hit) return;
    const norm = placing
      ? clientPointToOverlayNorm(e.clientX, e.clientY, rect, { clampToFrame: true })
      : normHit;
    if (!norm) {
      if (placing) skipPlayToggleRef.current = true;
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    skipPlayToggleRef.current = true;
    tableDragRef.current = {
      active: true,
      moved: Boolean(placing),
      pointerId: e.pointerId,
      start: { x: norm.x, y: norm.y },
    };
    setTableDragging(true);
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch (_err) {
      /* ignore */
    }
    tableUserRef.current = { x: norm.x, y: norm.y, source: "user" };
    setTableUserMark(tableUserRef.current);
    paintTableOverlay();
  };

  const onTablePointerMove = (e) => {
    const drag = tableDragRef.current;
    if (!drag.active || (drag.pointerId != null && e.pointerId !== drag.pointerId)) return;
    e.preventDefault();
    const rect = canvasRef.current?.getBoundingClientRect?.();
    const norm = clientPointToOverlayNorm(e.clientX, e.clientY, rect, { clampToFrame: true });
    if (!norm) return;
    if (drag.start && Math.abs(norm.x - drag.start.x) + Math.abs(norm.y - drag.start.y) > 0.006) {
      drag.moved = true;
    }
    tableUserRef.current = { x: norm.x, y: norm.y, source: "user" };
    paintTableOverlay();
  };

  const finishTableDrag = (e) => {
    const drag = tableDragRef.current;
    if (!drag.active) return false;
    if (e && drag.pointerId != null && e.pointerId !== drag.pointerId) return true;
    const rect = canvasRef.current?.getBoundingClientRect?.();
    const norm = e
      ? clientPointToOverlayNorm(e.clientX, e.clientY, rect, { clampToFrame: true })
      : null;
    const mark = norm || tableUserRef.current;
    if (mark) {
      const saved = saveTableUserMark(overlayDataRef.current, videoUrlRef.current, mark);
      tableUserRef.current = saved;
      setTableUserMark(saved);
    }
    tableDragRef.current = { active: false, moved: false, pointerId: null, start: null };
    setTableDragging(false);
    setTablePlaceMode(false);
    tablePlaceModeRef.current = false;
    skipPlayToggleRef.current = true;
    paintTableOverlay();
    return true;
  };

  /** Tap video stage to play/pause (ignore control chrome and table-mark drags). */
  const onVideoSurfacePointerUp = (e) => {
    if (finishTableDrag(e)) return;
    if (skipPlayToggleRef.current) {
      skipPlayToggleRef.current = false;
      return;
    }
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
    const video = videoRef.current;
    if (!video || !video.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX ?? e.nativeEvent?.changedTouches?.[0]?.clientX;
    if (clientX == null) return;
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    video.currentTime = pct * video.duration;
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
    setIsExpanded(false);
  }, []);

  const requestFullscreen = () => {
    if (isExpanded) {
      exitExpanded();
      return;
    }
    const video = videoRef.current;
    if (video) {
      savedTimeRef.current = video.currentTime;
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
    video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + step));
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
  }, [overlayStyle, showKinematicMarks, tablePlaceMode, drawOverlay]);

  useEffect(() => {
    autoRenderStartedRef.current = false;
    setDownloadUrl(null);
    setRenderProgress(0);
    cupLiveRef.current = null;
    cupTriesRef.current = 0;
  }, [videoUrl]);

  useEffect(() => {
    const m = loadTableUserMark(overlayData, videoUrl);
    tableUserRef.current = m;
    setTableUserMark(m);
    setTablePlaceMode(false);
    tablePlaceModeRef.current = false;
    tableDragRef.current = { active: false, moved: false, pointerId: null, start: null };
    setTableDragging(false);
  }, [videoUrl, overlayData?.overlay_video_filename]);

  useEffect(() => {
    tryAutoRender();
  }, [tryAutoRender]);

  useLayoutEffect(() => {
    const slot = slotRef.current;
    if (!slot) return undefined;
    let raf = 0;
    const update = () => {
      const next = readSlotBox(slot);
      setSlotBox((prev) => {
        if (
          prev &&
          next &&
          prev.left === next.left &&
          prev.top === next.top &&
          prev.width === next.width &&
          prev.height === next.height
        ) {
          return prev;
        }
        if (!prev && !next) return prev;
        return next;
      });
    };
    const updateRaf = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(update);
    };
    update();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateRaf) : null;
    if (ro) ro.observe(slot);
    window.addEventListener("scroll", updateRaf, true);
    window.addEventListener("resize", updateRaf);
    const vv = window.visualViewport;
    if (vv) {
      vv.addEventListener("resize", updateRaf);
      vv.addEventListener("scroll", updateRaf);
    }
    return () => {
      if (raf) cancelAnimationFrame(raf);
      if (ro) ro.disconnect();
      window.removeEventListener("scroll", updateRaf, true);
      window.removeEventListener("resize", updateRaf);
      if (vv) {
        vv.removeEventListener("resize", updateRaf);
        vv.removeEventListener("scroll", updateRaf);
      }
    };
  }, [videoUrl, isExpanded, videoAspect]);

  useEffect(() => {
    if (!isExpanded) return undefined;
    const id = requestAnimationFrame(() => {
      drawOverlay();
      window.dispatchEvent(new Event("resize"));
    });
    return () => cancelAnimationFrame(id);
  }, [isExpanded, drawOverlay]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.playbackRate = playbackRate;
  }, [playbackRate]);

  const controlsVisible = isExpanded || isTouchUi;
  const portalStyle = overlayPortalStyle({ isExpanded, slot: slotBox });

  const playerNode = (
    <div
      ref={containerRef}
      className={
        isExpanded
          ? "validation-player-fullscreen fixed inset-0 z-[99999] flex flex-col"
          : "relative w-full h-full rounded-lg overflow-hidden group flex flex-col justify-center items-center"
      }
      style={
        isExpanded
          ? { ...portalStyle, width: "100vw", height: "100dvh", maxWidth: "100vw", maxHeight: "100dvh" }
          : portalStyle
      }
    >
      {isExpanded && <AppShellBackground className="z-0" />}
      <div className="validation-player-chrome relative z-[1] flex flex-col flex-1 min-h-0 w-full">
      {isExpanded && (
        <div className="validation-player-topbar flex items-center justify-between px-4 pb-2.5 pt-[max(10px,env(safe-area-inset-top,0px))] flex-shrink-0 glass-float app-topbar-glass bg-white/[0.008] backdrop-blur-md backdrop-saturate-[2.25] border-b border-white/[0.03]">
          <p className="text-sm font-bold text-white/90 truncate pr-3">{phaseLabel || "Validation"} — Validation</p>
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

      <div className={`${isExpanded ? "validation-player-stage-area flex-1 flex min-h-0 w-full p-2 pb-0" : "relative w-full flex-1 min-h-0"}`}>
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
                    >
                      —
                    </span>
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
            }${tablePlaceMode ? " is-placing-table" : ""}${tableDragging ? " is-dragging-table" : ""}`}
            style={{ transform: "translateZ(0)", WebkitTransform: "translateZ(0)" }}
            onPointerDown={onTablePointerDown}
            onPointerMove={onTablePointerMove}
            onPointerUp={onVideoSurfacePointerUp}
            onPointerCancel={finishTableDrag}
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
                className={`block object-contain bg-transparent pointer-events-none ${
                  isExpanded ? "w-full h-full" : "w-full h-full max-w-full max-h-[80vh]"
                }`}
                onError={(e) => onError?.(e?.target?.error || new Error("Video failed to load"))}
              />
              <canvas
                ref={canvasRef}
                className="absolute pointer-events-none"
                style={{ transform: "translateZ(0)", WebkitTransform: "translateZ(0)" }}
              />
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
              onPointerDown={controlTap(() => setShowKinematicMarks((v) => !v))}
              className={`validation-control-btn validation-control-chip ${
                showKinematicMarks ? "is-active" : ""
              }`}
              aria-pressed={showKinematicMarks}
              title={showKinematicMarks ? "Hide marks on the drawing" : "Show marks on the drawing"}
            >
              Marks
            </button>
            <button
              type="button"
              onPointerDown={controlTap(onTableChip)}
              className={`validation-control-btn validation-control-chip ${
                tablePlaceMode ? "is-table-place is-active" : (tableUserMark ? "is-active" : "")
              }`}
              aria-pressed={Boolean(tablePlaceMode || tableUserMark)}
              title={
                tablePlaceMode
                  ? "Tap the table surface on the video, or tap Table to cancel"
                  : tableUserMark
                    ? "Table mark is set — tap to place it again, or drag the gold line"
                    : "Tap Table, then tap the table surface on the video. You can also drag the gold line."
              }
            >
              {tablePlaceMode ? "Tap table" : "Table"}
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
              <div className="validation-control-chip validation-control-busy">
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white/80 rounded-full animate-spin" />
                <span>{Math.round(renderProgress)}%</span>
              </div>
            ) : (
              <button
                type="button"
                onPointerDown={controlTap(() => { void handleDownload(); })}
                disabled={downloadBusy}
                className="validation-control-btn validation-control-chip validation-control-download"
                title={serverExportFilename || onRequestServerExport ? "Download validation video" : "Download overlay video"}
              >
                <Download className="w-4 h-4" />
                <span>{downloadBusy ? "…" : "Download"}</span>
              </button>
            )}
          </div>

          <div
            className="validation-seek-bar"
            onPointerDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
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

  const slotEl = (
    <div
      ref={slotRef}
      className="validation-player-slot"
      data-expanded={isExpanded ? "1" : "0"}
      style={overlaySlotReserveStyle(overlaySlotAspect(overlayData, videoAspect))}
      aria-hidden="true"
    />
  );

  // Always portal from first paint. Toggling expand used to move <video> onto
  // document.body; iPad then kept the overlay but lost the picture and controls.
  if (typeof document === "undefined" || !document.body) {
    return (
      <div className="relative w-full">
        {slotEl}
        {playerNode}
      </div>
    );
  }

  return (
    <>
      {slotEl}
      {createPortal(playerNode, document.body)}
    </>
  );
}

export default ValidationOverlayPlayer;
