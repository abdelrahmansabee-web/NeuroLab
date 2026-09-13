/** Visual evidence helpers: link tremor / pinch quality numbers to what the skeleton shows. */

import { formatTremorPower } from "./tremorMetrics";

/** Instantaneous tremor envelope intensity at frame idx (0–1-ish). */
export function localTremorEnvelopeAt(overlayData, idx) {
  const tp = overlayData?.tremor_profile;
  const win = overlayData?.movement_window;
  if (!tp?.v?.length || !win) return null;
  const local = idx - (win.start_idx || 0);
  if (local < 0 || local >= tp.v.length) return null;
  const v = Number(tp.v[local]);
  return Number.isFinite(v) ? Math.max(0, v) : null;
}

/** Short-window RMS of demeaned speed_tremor (fallback when no envelope). */
export function localTremorActivity(frames, idx, fps, shoulderWidthPx = 0) {
  if (!frames?.length || !fps) return null;
  const half = Math.max(4, Math.round(0.12 * fps));
  const a = Math.max(0, idx - half);
  const b = Math.min(frames.length - 1, idx + half);
  const sw = shoulderWidthPx > 0 ? shoulderWidthPx : 1;
  const vals = [];
  for (let i = a; i <= b; i += 1) {
    let s = frames[i]?.speed_tremor;
    if (s == null || Number.isNaN(s)) s = frames[i]?.speed ?? 0;
    vals.push(Number(s) / sw);
  }
  if (vals.length < 4) return null;
  const mu = vals.reduce((x, y) => x + y, 0) / vals.length;
  let ss = 0;
  for (const v of vals) ss += (v - mu) * (v - mu);
  return Math.sqrt(ss / vals.length);
}

export function pinchApertureFromFrame(frame, frameWidthPx, frameHeightPx, shoulderWidthPx) {
  if (!frame?.index || !frame?.thumb) return null;
  const ix = frame.index;
  const th = frame.thumb;
  if (ix[0] == null || ix[1] == null || th[0] == null || th[1] == null) return null;
  const fw = frameWidthPx > 0 ? frameWidthPx : 1;
  const fh = frameHeightPx > 0 ? frameHeightPx : 1;
  const dPx = Math.hypot((ix[0] - th[0]) * fw, (ix[1] - th[1]) * fh);
  const sw = shoulderWidthPx > 0 ? shoulderWidthPx : null;
  return {
    aperturePx: dPx,
    apertureSw: sw ? dPx / sw : null,
  };
}

/** Min/max pinch aperture (SW) over movement window for ROM ghost. */
export function pinchApertureWindowStats(frames, win, frameWidthPx, frameHeightPx, shoulderWidthPx) {
  if (!frames?.length || !win) return null;
  const start = Math.max(0, win.start_idx || 0);
  const end = Math.min(frames.length - 1, win.end_idx ?? frames.length - 1);
  let minSw = Infinity;
  let maxSw = -Infinity;
  let minFrame = null;
  let maxFrame = null;
  for (let i = start; i <= end; i += 1) {
    const a = pinchApertureFromFrame(frames[i], frameWidthPx, frameHeightPx, shoulderWidthPx);
    if (!a || a.apertureSw == null || !Number.isFinite(a.apertureSw)) continue;
    if (a.apertureSw < minSw) {
      minSw = a.apertureSw;
      minFrame = i;
    }
    if (a.apertureSw > maxSw) {
      maxSw = a.apertureSw;
      maxFrame = i;
    }
  }
  if (!Number.isFinite(minSw) || !Number.isFinite(maxSw) || minSw > maxSw) return null;
  return {
    minSw,
    maxSw,
    romSw: maxSw - minSw,
    minFrame,
    maxFrame,
  };
}

export function buildTremorEvidenceLines(overlayData, livePower, peakHz) {
  const m = overlayData?.metrics || {};
  const power = livePower ?? m.tremor_8_12hz_power ?? m.hand_speed_tremor_8_12hz_power;
  const peak = peakHz ?? m.tremor_peak_freq_hz;
  const lines = [];
  lines.push(`Tremor 8–12 Hz: ${formatTremorPower(power)}`);
  if (peak != null && Number.isFinite(Number(peak))) {
    lines.push(`Peak in band: ${Number(peak).toFixed(1)} Hz`);
  }
  lines.push("Source: palm speed FFT (not clinical IMU)");
  return lines;
}

export function buildPinchEvidenceLines(overlayData, liveApertureSw, romSw) {
  const m = overlayData?.metrics || {};
  const q = m.pinch_grasp_quality_index ?? m.adl_pinch_grasp_quality_index;
  const pinchTremor = m.pinch_tremor_8_12hz_power;
  const romStored = m.pinch_aperture_hl_rom_sw ?? romSw;
  const lines = [];
  if (q != null && Number.isFinite(Number(q))) {
    lines.push(`Pinch/grasp Q: ${Math.round(Number(q))}/100`);
  }
  if (liveApertureSw != null && Number.isFinite(liveApertureSw)) {
    lines.push(`Aperture now: ${liveApertureSw.toFixed(3)} SW`);
  }
  if (romStored != null && Number.isFinite(Number(romStored))) {
    lines.push(`Aperture ROM: ${Number(romStored).toFixed(3)} SW`);
  }
  if (pinchTremor != null && Number.isFinite(Number(pinchTremor))) {
    lines.push(`Pinch tremor: ${formatTremorPower(pinchTremor)}`);
  }
  const fm = m.fine_motor_quality_index;
  if (fm != null && Number.isFinite(Number(fm))) {
    const nvp = m.fine_motor_index_nvp;
    const stops = m.fine_motor_micro_stops;
    const cv = m.fine_motor_index_speed_cv;
    let fine = `Fine motor Q: ${Math.round(Number(fm))}`;
    const bits = [];
    if (nvp != null) bits.push(`NVP ${nvp}`);
    if (stops != null) bits.push(`stops ${stops}`);
    if (cv != null && Number.isFinite(Number(cv))) bits.push(`CV ${Number(cv).toFixed(2)}`);
    if (bits.length) fine += ` (${bits.join(", ")})`;
    lines.push(fine);
  }
  if (!lines.length) {
    lines.push("Pinch evidence needs Hand Landmarker tips");
  } else {
    lines.push("Q ↑ when ROM ↑ and tremor/CV ↓");
  }
  return lines;
}

/**
 * Draw multi-line evidence card near an anchor point.
 */
export function drawEvidenceCard(ctx, lines, anchor, opts = {}) {
  if (!ctx || !lines?.length || !anchor) return;
  const {
    cw,
    ch,
    offsetX = 14,
    offsetY = -70,
    dpr = 1,
    bg = "rgba(10,14,22,0.88)",
    border = "rgba(148,163,184,0.45)",
    titleColor = "#e2e8f0",
  } = opts;
  const fontSize = Math.round(10 * dpr);
  const pad = 6 * dpr;
  const lineH = Math.round(13 * dpr);
  ctx.save();
  ctx.font = `600 ${fontSize}px ui-sans-serif, system-ui, sans-serif`;
  let maxW = 0;
  lines.forEach((t) => {
    maxW = Math.max(maxW, ctx.measureText(t).width);
  });
  const w = maxW + pad * 2;
  const h = lines.length * lineH + pad * 2;
  let x = anchor[0] + offsetX;
  let y = anchor[1] + offsetY;
  x = Math.max(4, Math.min(cw - w - 4, x));
  y = Math.max(4, Math.min(ch - h - 4, y));
  const rr = 6 * dpr;
  ctx.fillStyle = bg;
  ctx.strokeStyle = border;
  ctx.lineWidth = 1;
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
  lines.forEach((t, i) => {
    ctx.fillStyle = i === 0 ? titleColor : "rgba(226,232,240,0.88)";
    ctx.fillText(t, x + pad, y + pad + (i + 0.78) * lineH);
  });
  ctx.restore();
}
