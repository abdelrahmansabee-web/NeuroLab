/**
 * Single source of truth for UE validation-video panel numbers.
 * The kinematics table, overlay_metrics, and the live panel all read these formulas.
 */
import {
  computeLiveTremorPower,
  formatTremorAmplitude,
  formatTremorPower,
  resolveTremorMetrics,
} from "./tremorMetrics";

/** Table / report keys that must copy the validation-video panel (not server SPSS fields). */
export const PANEL_TABLE_KEYS = [
  "nvp",
  "movement_time_sec",
  "straightness",
  "peak_velocity_cm_s",
  "peak_elbow_ang_vel_deg_s",
  "pause_time_sec",
  "number_of_stops",
  "trunk_ratio",
  "shoulder_elevation_cm",
  "shoulder_elevation_palm_ratio",
  "shoulder_elevation_table_ratio",
  "shoulder_elevation_norm",
  "shoulder_vert_norm",
  "elbow_angle_mean_deg",
  "tremor_8_12hz_power",
  "tremor_peak_freq_hz",
  "tremor_index",
  "movement_quality_index",
  "fine_motor_quality_index",
];

const PANEL_TABLE_KEY_SET = new Set(PANEL_TABLE_KEYS);

export function isPanelTableKey(metricKey) {
  return PANEL_TABLE_KEY_SET.has(metricKey);
}

export function pickOverlayMetric(overlayData, keys) {
  const m = overlayData?.metrics || {};
  for (const k of keys) {
    const v = m[k];
    if (v != null && v !== "" && !Number.isNaN(Number(v))) return Number(v);
  }
  return null;
}

export function overlayMovementWindow(overlayData) {
  const frames = overlayData?.frames || [];
  const last = Math.max(0, frames.length - 1);
  const win = overlayData?.movement_window || { start_idx: 0, end_idx: last };
  const startIdx = Math.max(0, Math.min(last, win.start_idx || 0));
  const endIdx = Math.max(startIdx, Math.min(last, win.end_idx ?? last));
  return { startIdx, endIdx };
}

function xyPair(pt) {
  if (!pt || pt[0] == null || pt[1] == null) return null;
  const x = Number(pt[0]);
  const y = Number(pt[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

/**
 * Hand path for NVP / straightness: rest wrist landmark, never the overlay
 * display palm (that field is the index tip).
 */
export function pathLandmarkXY(frame) {
  return xyPair(frame?.wrist) || xyPair(frame?.hl_wrist) || xyPair(frame?.palm);
}

function medianNum(vals) {
  const a = vals.filter((v) => Number.isFinite(v)).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

/**
 * Rest hand landmark: wrist on the table before the reach.
 * Never the overlay `palm` field first — that is the index tip used only to draw fingers.
 */
export function restLandmarkPalm(overlayData) {
  const stored = xyPair(overlayData?.rest_wrist);
  if (stored) return stored;
  const frames = overlayData?.frames || [];
  if (!frames.length) {
    return xyPair(overlayData?.start_wrist) || xyPair(overlayData?.start_palm);
  }
  const { startIdx } = overlayMovementWindow(overlayData);
  const fps = Number(overlayData?.fps) || 60;
  const earlyN = Math.max(1, Math.round(fps * 0.2));
  const hi = Math.max(0, Math.min(frames.length - 1, startIdx > 0 ? Math.min(startIdx, earlyN) : 0));
  const xs = [];
  const ys = [];
  for (let i = 0; i <= hi; i += 1) {
    const p = pathLandmarkXY(frames[i]);
    if (p) {
      xs.push(p[0]);
      ys.push(p[1]);
    }
  }
  const mx = medianNum(xs);
  const my = medianNum(ys);
  if (mx != null && my != null) return [mx, my];
  return (
    xyPair(overlayData?.start_wrist)
    || pathLandmarkXY(frames[startIdx])
    || xyPair(overlayData?.start_palm)
  );
}

function restLeaveEps(overlayData, restPalm) {
  const frames = overlayData?.frames || [];
  const { endIdx } = overlayMovementWindow(overlayData);
  const endP = pathLandmarkXY(frames[endIdx]);
  if (restPalm && endP) {
    const reach = Math.hypot(endP[0] - restPalm[0], endP[1] - restPalm[1]);
    if (reach > 1e-6) return Math.max(reach * 0.05, 1e-4);
  }
  return 0.02;
}

/** Frame of the rest landmark — last palm still at rest before the hand leaves it. */
export function restPathStartIdx(overlayData) {
  const frames = overlayData?.frames || [];
  const { startIdx } = overlayMovementWindow(overlayData);
  if (!frames.length) return 0;
  if (Number.isFinite(Number(overlayData?.rest_idx))) {
    return Math.max(0, Math.min(frames.length - 1, Number(overlayData.rest_idx)));
  }
  const rest = restLandmarkPalm(overlayData);
  if (!rest) return startIdx;
  const eps = restLeaveEps(overlayData, rest);
  const last = Math.min(startIdx, frames.length - 1);
  let firstLeave = null;
  for (let i = 0; i <= last; i += 1) {
    const p = pathLandmarkXY(frames[i]);
    if (!p) continue;
    if (Math.hypot(p[0] - rest[0], p[1] - rest[1]) > eps) {
      firstLeave = i;
      break;
    }
  }
  if (firstLeave == null) return startIdx;
  return Math.max(0, firstLeave - 1);
}

function palmDeltaSpeed(frames, fps, i) {
  if (i <= 0) return 0;
  const a = pathLandmarkXY(frames[i - 1]);
  const b = pathLandmarkXY(frames[i]);
  if (!a || !b) return 0;
  return Math.hypot(b[0] - a[0], b[1] - a[1]) * fps;
}

function sampleHandSpeed(frames, fps, i) {
  const baked = Number(frames[i]?.speed);
  if (Number.isFinite(baked) && baked > 0) return baked;
  return palmDeltaSpeed(frames, fps, i);
}

function localMaxima(values, prominence) {
  const out = [];
  for (let i = 1; i < values.length - 1; i += 1) {
    const v = values[i];
    if (v > values[i - 1] && v >= values[i + 1] && v >= prominence) out.push(i);
  }
  return out;
}

/**
 * Overlay peak_frames miss rest→onset (bake zeros speed there). Fill that gap
 * from the visible rest-palm path so NVP starts at the rest landmark.
 */
export function nvpPeakIndicesFromRest(overlayData, untilIdx) {
  const frames = overlayData?.frames || [];
  const { startIdx, endIdx } = overlayMovementWindow(overlayData);
  const restIdx = restPathStartIdx(overlayData);
  const hi = Math.min(
    frames.length - 1,
    Number.isFinite(Number(untilIdx)) ? Number(untilIdx) : endIdx,
    endIdx,
  );
  const baked = nvpPeakIndicesInWindow(overlayData?.peak_frames, restIdx, hi);
  if (restIdx >= startIdx) return baked;
  const fps = Number(overlayData?.fps) || 60;
  const speeds = [];
  for (let i = restIdx; i <= hi; i += 1) speeds.push(sampleHandSpeed(frames, fps, i));
  const mean = speeds.length ? speeds.reduce((s, v) => s + v, 0) / speeds.length : 0;
  const varr = speeds.length
    ? speeds.reduce((s, v) => s + (v - mean) ** 2, 0) / speeds.length
    : 0;
  const std = Math.sqrt(varr);
  const peak = speeds.length ? Math.max(...speeds) : 0;
  const prominence = std > 0 ? std * 0.30 : peak * 0.05;
  const early = new Set(baked);
  localMaxima(speeds, prominence).forEach((local) => {
    const gi = restIdx + local;
    if (gi >= restIdx && gi < startIdx && gi <= hi) early.add(gi);
  });
  return [...early].sort((a, b) => a - b);
}

export function countNvpPeaksFromRest(overlayData, untilIdx) {
  return nvpPeakIndicesFromRest(overlayData, untilIdx).length;
}

export function straightnessFromRest(overlayData, untilIdx) {
  const frames = overlayData?.frames || [];
  if (!frames.length) return 0;
  const restPalm = restLandmarkPalm(overlayData);
  const restIdx = restPathStartIdx(overlayData);
  const { endIdx } = overlayMovementWindow(overlayData);
  const hi = Math.min(
    frames.length - 1,
    Number.isFinite(Number(untilIdx)) ? Number(untilIdx) : endIdx,
    endIdx,
  );
  if (hi < restIdx || !restPalm) return 0;
  let pathLength = 0;
  let prev = restPalm;
  for (let i = restIdx; i <= hi; i += 1) {
    const curr = pathLandmarkXY(frames[i]);
    if (!prev || !curr) {
      if (curr) prev = curr;
      continue;
    }
    pathLength += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
    prev = curr;
  }
  const endP = pathLandmarkXY(frames[hi]);
  if (!endP || pathLength <= 0) return 0;
  const displacement = Math.hypot(endP[0] - restPalm[0], endP[1] - restPalm[1]);
  return Math.min(1, displacement / pathLength);
}

function angleBetweenDeg(v1, v2) {
  const n1 = Math.hypot(v1[0], v1[1]);
  const n2 = Math.hypot(v2[0], v2[1]);
  if (n1 < 1e-6 || n2 < 1e-6) return null;
  const cos = Math.max(-1, Math.min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)));
  return (Math.acos(cos) * 180) / Math.PI;
}

function sameSideHip(frame, affectedSide) {
  const side = String(affectedSide || "").toLowerCase();
  const left = side.startsWith("l");
  const primary = xyPair(left ? frame?.lhip : frame?.rhip);
  if (primary) return primary;
  const secondary = xyPair(left ? frame?.rhip : frame?.lhip);
  if (secondary) return secondary;
  const lh = xyPair(frame?.lhip);
  const rh = xyPair(frame?.rhip);
  if (lh && rh) return [(lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2];
  return null;
}

/**
 * Clinical goniometer shoulder flexion in the image plane:
 * stationary arm = midaxillary line (shoulder → same-side hip),
 * moving arm = humerus (shoulder → elbow / lateral epicondyle).
 * 0° = arm alongside the trunk.
 */
export function shoulderFlexionGoniometerDeg(frame, affectedSide) {
  const sh = xyPair(frame?.shoulder);
  const el = xyPair(frame?.elbow);
  if (!sh || !el) return null;
  const hip = sameSideHip(frame, affectedSide);
  let stat = hip ? [hip[0] - sh[0], hip[1] - sh[1]] : null;
  if (!stat || Math.hypot(stat[0], stat[1]) < 1e-4) {
    stat = [0, 1];
  }
  return angleBetweenDeg(stat, [el[0] - sh[0], el[1] - sh[1]]);
}

export function meanShoulderFlexionGoniometer(frames, startIdx, endIdx, affectedSide) {
  const vals = [];
  const last = Math.min(endIdx, (frames?.length || 1) - 1);
  const lo = Math.max(0, startIdx);
  for (let i = lo; i <= last; i += 1) {
    const a = shoulderFlexionGoniometerDeg(frames[i], affectedSide);
    if (a != null && Number.isFinite(a)) vals.push(a);
  }
  if (!vals.length) return null;
  return vals.reduce((s, v) => s + v, 0) / vals.length;
}

/** Peaks on the path from onset through untilIdx — same gate as overlay NVP dots. */
export function nvpPeakIndicesInWindow(peakFrames, startIdx, untilIdx) {
  const lo = Number(startIdx);
  const hi = Number(untilIdx);
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  return (peakFrames || []).filter((pi) => {
    const n = Number(pi);
    return Number.isFinite(n) && n >= lo && n <= hi;
  });
}

export function countNvpPeaksInWindow(peakFrames, startIdx, untilIdx) {
  return nvpPeakIndicesInWindow(peakFrames, startIdx, untilIdx).length;
}

/** 5% of whole-clip peak hand speed — same pause gate as the live panel. */
export function overlayPauseSpeedThreshold(frames) {
  let peak = 0;
  if (frames?.length) {
    for (let i = 0; i < frames.length; i += 1) peak = Math.max(peak, frames[i]?.speed || 0);
  }
  return peak > 0 ? 0.05 * peak : 1.0;
}

export function elbowAngVelAt(frames, fps, idx) {
  if (idx <= 0 || idx >= frames.length) return 0;
  const a1 = frames[idx - 1]?.elbow_angle;
  const a2 = frames[idx]?.elbow_angle;
  if (a1 == null || a2 == null) return 0;
  const dt = (frames[idx]?.time != null && frames[idx - 1]?.time != null)
    ? Math.max(1e-6, frames[idx].time - frames[idx - 1].time)
    : 1 / fps;
  return Math.abs((a2 - a1) / dt);
}

export function computeLiveFingerQuality(frames, startIdx, idx) {
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

function clampFrameIdx(frames, idx) {
  if (!frames.length) return 0;
  return Math.max(0, Math.min(frames.length - 1, idx));
}

function assignIfNum(out, key, v) {
  if (v == null || v === "") return;
  const n = Number(v);
  if (Number.isNaN(n)) return;
  out[key] = n;
}

/**
 * Exact UE validation-video panel numbers at frame `untilIdx`.
 * Omit untilIdx (or pass null) to snapshot the movement-window end — what the
 * kinematics table must show.
 *
 * Pause/stops: every frame below 5% of whole-clip peak hand speed, no min-run
 * length and no terminal-dwell split (same as the live panel).
 * Peak elbow °/s: max from frame 1 through untilIdx (not window-only).
 * Shoulder rows: current frame at untilIdx (not max-over-window).
 */
export function computeValidationPanelLive(overlayData, untilIdx) {
  if (!overlayData?.frames?.length) return null;
  const frames = overlayData.frames;
  const fps = overlayData.fps || 60;
  const { startIdx, endIdx } = overlayMovementWindow(overlayData);
  const idx = untilIdx == null || Number.isNaN(Number(untilIdx))
    ? endIdx
    : clampFrameIdx(frames, Number(untilIdx));
  const f = frames[idx] || {};

  const speedThreshold = overlayPauseSpeedThreshold(frames);
  const inMovement = idx >= startIdx && idx <= endIdx;
  const t0 = startIdx < frames.length ? (frames[startIdx].time || startIdx / fps) : 0;

  const restIdx = restPathStartIdx(overlayData);
  const restPalm = restLandmarkPalm(overlayData);
  const nvp = countNvpPeaksFromRest(overlayData, Math.min(idx, endIdx));

  let peakElbowAngVel = 0;
  for (let i = 1; i <= idx && i < frames.length; i += 1) {
    peakElbowAngVel = Math.max(peakElbowAngVel, elbowAngVelAt(frames, fps, i));
  }

  let movementTime = 0;
  if (inMovement && idx < frames.length) {
    const t = frames[idx].time || idx / fps;
    movementTime = Math.max(0, t - t0);
  }

  let pauseTime = 0;
  let stops = 0;
  for (let i = startIdx; i <= idx && i < frames.length; i += 1) {
    const s = frames[i].speed || 0;
    if (s < speedThreshold) pauseTime += 1 / fps;
    if (i > startIdx) {
      const prevS = frames[i - 1].speed || 0;
      if (prevS >= speedThreshold && s < speedThreshold) stops += 1;
    }
  }

  const straightness = idx >= restIdx ? straightnessFromRest(overlayData, Math.min(idx, endIdx)) : 0;

  let trunkRatio = 0;
  if (inMovement) {
    const trunkStart = frames[startIdx]?.trunk;
    const trunkEnd = frames[idx]?.trunk;
    const palmStart = frames[startIdx]?.palm;
    const palmEnd = frames[idx]?.palm;
    if (trunkStart && trunkEnd && palmStart && palmEnd) {
      const trunkDisp = Math.abs(trunkEnd[0] - trunkStart[0]);
      const palmDisp = Math.hypot(palmEnd[0] - palmStart[0], palmEnd[1] - palmStart[1]);
      if (palmDisp > 0) trunkRatio = Math.min(1, trunkDisp / palmDisp);
    }
  }

  let shoulderElevation = 0;
  if (typeof f.shoulder_elevation_norm === "number" && !Number.isNaN(f.shoulder_elevation_norm)) {
    shoulderElevation = f.shoulder_elevation_norm;
  }
  let shoulderElevationTable = 0;
  if (typeof f.shoulder_elevation_table_ratio === "number" && !Number.isNaN(f.shoulder_elevation_table_ratio)) {
    shoulderElevationTable = f.shoulder_elevation_table_ratio;
  }
  let shoulderElevationPalm = 0;
  if (typeof f.shoulder_elevation_palm_ratio === "number" && !Number.isNaN(f.shoulder_elevation_palm_ratio)) {
    shoulderElevationPalm = f.shoulder_elevation_palm_ratio;
  }

  let shoulderAbduction = 0;
  if (typeof f.shoulder_abduction_deg === "number" && f.shoulder_abduction_deg > 0) {
    shoulderAbduction = f.shoulder_abduction_deg;
  }

  const adlStart = overlayData?.adl_window?.start_idx ?? startIdx;
  const fingerQuality = computeLiveFingerQuality(frames, adlStart, idx) ?? 0;

  const tremorLive = computeLiveTremorPower(
    frames,
    fps,
    startIdx,
    Math.max(startIdx, idx),
    overlayData?.shoulder_width_px || 0,
    overlayData,
  );
  let adlTremorLive = null;
  if (overlayData?.adl_window) {
    adlTremorLive = computeLiveTremorPower(
      frames,
      fps,
      overlayData.adl_window.start_idx ?? startIdx,
      Math.max(overlayData.adl_window.start_idx ?? startIdx, idx),
      overlayData?.shoulder_width_px || 0,
      overlayData,
    );
  }
  const resolvedTremor = resolveTremorMetrics(overlayData);

  const peakVelocityCmS = pickOverlayMetric(overlayData, ["peak_velocity_cm_s"]);
  const shoulderElevationCm = pickOverlayMetric(overlayData, ["shoulder_elevation_cm"]);
  const elbowMean = pickOverlayMetric(overlayData, ["elbow_angle_mean_deg", "elbow_angle_mean"]);
  const movementQuality = overlayData?.metrics?.movement_quality_index
    ?? pickOverlayMetric(overlayData, ["movement_quality_index"]);

  return {
    idx,
    startIdx,
    endIdx,
    nvp,
    restIdx,
    restPalm,
    movementTime,
    straightness,
    peakElbowAngVel,
    pauseTime,
    stops,
    trunkRatio,
    shoulderElevation,
    shoulderElevationTable,
    shoulderElevationPalm,
    shoulderAbduction,
    fingerQuality,
    peakVelocityCmS: peakVelocityCmS != null && Number(peakVelocityCmS) > 0 ? Number(peakVelocityCmS) : null,
    shoulderElevationCm: shoulderElevationCm != null && Number(shoulderElevationCm) > 0 ? Number(shoulderElevationCm) : null,
    elbowAngleMeanDeg: elbowMean,
    tremor_8_12hz_power:
      idx >= endIdx
        ? resolvedTremor?.tremor_8_12hz_power
        : tremorLive?.tremor_8_12hz_power ?? resolvedTremor?.tremor_8_12hz_power,
    tremor_abs_rms_px:
      idx >= endIdx
        ? resolvedTremor?.tremor_abs_rms_px
        : tremorLive?.tremor_abs_rms_px ?? resolvedTremor?.tremor_abs_rms_px,
    tremor_abs_rms_sw:
      idx >= endIdx
        ? resolvedTremor?.tremor_abs_rms_sw
        : tremorLive?.tremor_abs_rms_sw ?? resolvedTremor?.tremor_abs_rms_sw,
    tremor_present:
      idx >= endIdx
        ? resolvedTremor?.tremor_present
        : tremorLive?.tremor_present ?? resolvedTremor?.tremor_present,
    tremor_index:
      idx >= endIdx
        ? resolvedTremor?.tremor_index
        : tremorLive?.tremor_index ?? resolvedTremor?.tremor_index,
    index_tremor_8_12hz_power: resolvedTremor?.index_tremor_8_12hz_power,
    tremor_peak_freq_hz:
      idx >= endIdx
        ? resolvedTremor?.tremor_peak_freq_hz
        : tremorLive?.tremor_peak_freq_hz ?? resolvedTremor?.tremor_peak_freq_hz,
    movement_quality_index: movementQuality,
    adl_tremor_8_12hz_power:
      adlTremorLive?.tremor_8_12hz_power
      ?? resolvedTremor?.adl_tremor_8_12hz_power
      ?? tremorLive?.tremor_8_12hz_power
      ?? resolvedTremor?.tremor_8_12hz_power,
    shoulder_width_px: Number(overlayData?.shoulder_width_px) || 0,
    ...computeClinicPanelLive(overlayData, idx),
  };
}

function panelToOverlayMetrics(panel) {
  if (!panel) return null;
  const out = {};
  assignIfNum(out, "nvp", panel.nvp);
  assignIfNum(out, "nvp_reach", panel.nvp);
  assignIfNum(out, "straightness", panel.straightness);
  assignIfNum(out, "pause_time_sec", panel.pauseTime);
  assignIfNum(out, "number_of_stops", panel.stops);
  assignIfNum(out, "trunk_ratio", panel.trunkRatio);
  assignIfNum(out, "shoulder_elevation_norm", panel.shoulderElevation);
  assignIfNum(out, "shoulder_vert_norm", panel.shoulderElevation);
  assignIfNum(out, "shoulder_elevation_table_ratio", panel.shoulderElevationTable);
  assignIfNum(out, "shoulder_elevation_palm_ratio", panel.shoulderElevationPalm);
  assignIfNum(out, "shoulder_elevation_cm", panel.shoulderElevationCm);
  assignIfNum(out, "peak_velocity_cm_s", panel.peakVelocityCmS);
  assignIfNum(out, "elbow_angle_mean_deg", panel.elbowAngleMeanDeg);
  assignIfNum(out, "movement_time_sec", panel.movementTime);
  assignIfNum(out, "peak_elbow_ang_vel_deg_s", panel.peakElbowAngVel);
  assignIfNum(out, "tremor_8_12hz_power", panel.tremor_8_12hz_power);
  assignIfNum(out, "tremor_abs_rms_px", panel.tremor_abs_rms_px);
  assignIfNum(out, "tremor_abs_rms_sw", panel.tremor_abs_rms_sw);
  if (panel.tremor_present === true || panel.tremor_present === false) {
    out.tremor_present = panel.tremor_present;
  }
  assignIfNum(out, "shoulder_width_px", panel.shoulder_width_px);
  assignIfNum(out, "tremor_index", panel.tremor_index);
  assignIfNum(out, "tremor_peak_freq_hz", panel.tremor_peak_freq_hz);
  assignIfNum(out, "index_tremor_8_12hz_power", panel.index_tremor_8_12hz_power);
  assignIfNum(out, "adl_tremor_8_12hz_power", panel.adl_tremor_8_12hz_power);
  assignIfNum(out, "movement_quality_index", panel.movement_quality_index);
  if (panel.fingerQuality > 0) assignIfNum(out, "fine_motor_quality_index", panel.fingerQuality);
  return out;
}

/** SPSS / exploratory keys that are not on the UE validation panel. */
function computeExploratoryExtras(overlayData) {
  const frames = overlayData.frames;
  const fps = overlayData.fps || 60;
  const { startIdx, endIdx } = overlayMovementWindow(overlayData);
  const t0 = frames[startIdx]?.time != null ? frames[startIdx].time : startIdx / fps;

  let peakElbowIdx = startIdx;
  let peakElbowAngVel = 0;
  for (let i = 1; i <= endIdx && i < frames.length; i += 1) {
    const angVel = elbowAngVelAt(frames, fps, i);
    if (angVel > peakElbowAngVel) {
      peakElbowAngVel = angVel;
      peakElbowIdx = i;
    }
  }
  const tPeak = frames[peakElbowIdx]?.time != null ? frames[peakElbowIdx].time : peakElbowIdx / fps;
  const timeToPeak = Math.max(0, tPeak - t0);

  const winSpeeds = frames.slice(startIdx, endIdx + 1).map((fr) => fr.speed || 0);
  const winPeakV = winSpeeds.length ? Math.max(...winSpeeds) : 0;
  const speedThreshold = winPeakV > 0 ? 0.05 * winPeakV : 1.0;
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
  const graspDwellSec = sumFrames(dwellRuns) / fps;

  const extras = {
    time_to_peak_velocity_sec: timeToPeak,
    grasp_dwell_sec: graspDwellSec,
  };
  const movementTime = (() => {
    const t1 = frames[endIdx]?.time != null ? frames[endIdx].time : endIdx / fps;
    return Math.max(0, t1 - t0);
  })();
  if (movementTime > 0) extras.relative_time_to_peak_pct = (timeToPeak / movementTime) * 100;
  return extras;
}

/** Running clinic SPSS numbers from movement onset through untilIdx (live panel). */
function computeClinicPanelLive(overlayData, untilIdx) {
  const frames = overlayData?.frames || [];
  if (!frames.length) return {};
  const { startIdx, endIdx } = overlayMovementWindow(overlayData);
  const idx = untilIdx == null || Number.isNaN(Number(untilIdx))
    ? endIdx
    : clampFrameIdx(frames, Number(untilIdx));
  if (idx < startIdx) return {};
  const until = Math.max(startIdx, Math.min(idx, endIdx));
  const cm = overlayCmPerPx(overlayData);
  const sw = Number(overlayData?.shoulder_width_px) || Number(overlayData?.metrics?.shoulder_width_px) || 0;
  const out = {};

  if (cm != null) {
    const speed = windowSeriesStats(frames, startIdx, until, "speed");
    if (speed.mean != null) out.liveAverageHandVelocityCmS = speed.mean * cm;
    const trunk = windowSeriesStats(frames, startIdx, until, "trunk_displacement_norm");
    if (trunk.max != null && sw > 0) {
      out.liveTrunkForwardDisplacementCm = trunk.max * sw * cm;
    } else {
      const a = frames[startIdx]?.trunk;
      const b = frames[until]?.trunk;
      if (a && b && a[0] != null && b[0] != null && sw > 0) {
        out.liveTrunkForwardDisplacementCm = Math.abs(b[0] - a[0]) * sw * cm;
      }
    }
    const elev = windowSeriesStats(frames, startIdx, until, "shoulder_elevation_norm");
    if (elev.max != null && sw > 0) {
      out.liveShoulderElevationCm = elev.max * sw * cm;
    }
  }

  const elbow = windowSeriesStats(frames, startIdx, until, "elbow_angle", { skipNonPositive: true });
  if (elbow.mean != null) out.liveElbowAngleMeanDeg = elbow.mean;
  const gonio = meanShoulderFlexionGoniometer(frames, startIdx, until, overlayData?.affected_side);
  if (gonio != null) {
    out.liveShoulderFlexionMeanDeg = gonio;
  } else {
    const flex = windowSeriesStats(frames, startIdx, until, "shoulder_flexion_deg", { skipNonPositive: true });
    if (flex.mean != null) out.liveShoulderFlexionMeanDeg = flex.mean;
  }
  const abd = windowSeriesStats(frames, startIdx, until, "shoulder_abduction_deg", { skipNonPositive: true });
  if (abd.mean != null) out.liveShoulderAbductionMeanDeg = abd.mean;
  return out;
}

function windowSeriesStats(frames, startIdx, endIdx, key, { skipNonPositive = false } = {}) {
  const vals = [];
  let max = -Infinity;
  const last = Math.min(endIdx, (frames?.length || 1) - 1);
  for (let i = startIdx; i <= last; i += 1) {
    const v = Number(frames[i]?.[key]);
    if (!Number.isFinite(v)) continue;
    if (skipNonPositive && !(v > 0)) continue;
    vals.push(v);
    if (v > max) max = v;
  }
  if (!vals.length) return { mean: null, max: null };
  return {
    mean: vals.reduce((a, b) => a + b, 0) / vals.length,
    max: max === -Infinity ? null : max,
  };
}

function overlayCmPerPx(overlayData) {
  const candidates = [
    overlayData?.cm_per_px,
    overlayData?.metrics?.cm_per_px,
    overlayData?.table_scale?.cm_per_px,
  ];
  for (const c of candidates) {
    const n = Number(c);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return null;
}

/** Fill requested clinic keys from existing overlay frames when the backend left them blank. */
export function fillMissingClinicOverlaySummaries(overlayData, out = {}) {
  if (!overlayData?.frames?.length) return out;
  const frames = overlayData.frames;
  const { startIdx, endIdx } = overlayMovementWindow(overlayData);
  const cm = overlayCmPerPx(overlayData);
  const sw = Number(overlayData?.shoulder_width_px) || Number(overlayData?.metrics?.shoulder_width_px) || 0;

  if (out.average_hand_velocity_cm_s == null && cm != null) {
    const speed = windowSeriesStats(frames, startIdx, endIdx, "speed");
    if (speed.mean != null) out.average_hand_velocity_cm_s = speed.mean * cm;
  }
  if (out.trunk_forward_displacement_cm == null && cm != null) {
    const trunk = windowSeriesStats(frames, startIdx, endIdx, "trunk_displacement_norm");
    if (trunk.max != null && sw > 0) {
      out.trunk_forward_displacement_cm = trunk.max * sw * cm;
    }
  }
  const gonio = meanShoulderFlexionGoniometer(frames, startIdx, endIdx, overlayData?.affected_side);
  if (gonio != null) {
    out.shoulder_flexion_mean_deg = gonio;
  } else if (out.shoulder_flexion_mean_deg == null) {
    const flex = windowSeriesStats(frames, startIdx, endIdx, "shoulder_flexion_deg", { skipNonPositive: true });
    if (flex.mean != null) out.shoulder_flexion_mean_deg = flex.mean;
  }
  if (out.shoulder_abduction_mean_deg == null) {
    const abd = windowSeriesStats(frames, startIdx, endIdx, "shoulder_abduction_deg", { skipNonPositive: true });
    if (abd.mean != null) out.shoulder_abduction_mean_deg = abd.mean;
  }
  if (out.elbow_angle_mean_deg == null) {
    const elbow = windowSeriesStats(frames, startIdx, endIdx, "elbow_angle", { skipNonPositive: true });
    if (elbow.mean != null) out.elbow_angle_mean_deg = elbow.mean;
  }
  return out;
}

const overlayMetricsCache = new WeakMap();

/**
 * Snapshot of the validation panel at movement-window end, plus backend-only extras.
 * Overlapping keys always come from the panel — never from a different pause/NVP formula.
 */
export function computeOverlayMetrics(overlayData) {
  if (!overlayData?.frames?.length) return null;
  const cached = overlayMetricsCache.get(overlayData);
  if (cached) return cached;

  const { endIdx } = overlayMovementWindow(overlayData);
  const panel = computeValidationPanelLive(overlayData, endIdx);
  const out = panelToOverlayMetrics(panel) || {};
  Object.assign(out, computeExploratoryExtras(overlayData));

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
      "shoulder_flexion_mean_deg",
      "average_hand_velocity_cm_s",
      "trunk_forward_displacement_cm",
      "mean_hand_speed_px_s",
      "nvp_total",
      "cm_per_px",
    ];
    for (const k of passthrough) {
      if (backend[k] != null && backend[k] !== "") out[k] = backend[k];
    }
  }

  fillMissingClinicOverlaySummaries(overlayData, out);

  overlayMetricsCache.set(overlayData, out);
  return out;
}

function formatFixed(v, digits) {
  if (v == null || Number.isNaN(Number(v))) return "\u2014";
  if (digits === 0) return Math.round(Number(v)).toString();
  return Number(v).toFixed(digits);
}

/**
 * Format a panel-sourced table cell the same way the validation-video panel paints it.
 */
export function formatPanelAlignedKinValue(metricKey, value, overlayMetrics = null) {
  const om = overlayMetrics || {};
  if (metricKey === "peak_velocity_cm_s") {
    const cm = value != null && Number(value) > 0 ? Number(value) : (om.peak_velocity_cm_s != null && Number(om.peak_velocity_cm_s) > 0 ? Number(om.peak_velocity_cm_s) : null);
    if (cm != null) return formatFixed(cm, 1);
    const deg = om.peak_elbow_ang_vel_deg_s;
    if (deg != null && Number(deg) > 0) return `${Math.round(Number(deg))} \u00b0/s`;
    return "\u2014";
  }
  if (metricKey === "shoulder_elevation_cm") {
    const cm = value != null && Number(value) > 0 ? Number(value) : (om.shoulder_elevation_cm != null && Number(om.shoulder_elevation_cm) > 0 ? Number(om.shoulder_elevation_cm) : null);
    if (cm != null) return formatFixed(cm, 1);
    const ratio = (om.shoulder_elevation_palm_ratio && Number(om.shoulder_elevation_palm_ratio) > 0)
      ? om.shoulder_elevation_palm_ratio
      : (om.shoulder_elevation_table_ratio && Number(om.shoulder_elevation_table_ratio) > 0)
        ? om.shoulder_elevation_table_ratio
        : (om.shoulder_elevation_norm && Number(om.shoulder_elevation_norm) > 0)
          ? om.shoulder_elevation_norm
          : null;
    if (ratio != null) return formatFixed(ratio, 3);
    return "\u2014";
  }
  if (metricKey === "pause_stops_panel") {
    const pt = om.pause_time_sec;
    const ns = om.number_of_stops;
    if (!(Number(pt) > 0 || Number(ns) > 0)) return "\u2014";
    return `${formatFixed(pt || 0, 2)} s / ${Math.round(Number(ns) || 0)}`;
  }

  if (value == null || value === "\u2014" || Number.isNaN(Number(value))) return "\u2014";
  const val = Number(value);
  if (metricKey === "nvp" || metricKey === "nvp_reach" || metricKey === "nvp_drink"
    || metricKey === "nvp_transport" || metricKey === "nvp_return" || metricKey === "nvp_total"
    || metricKey === "number_of_stops") return formatFixed(val, 0);
  if (metricKey === "straightness" || metricKey === "trunk_ratio" || metricKey === "movement_time_sec") {
    if (val <= 0) return "\u2014";
    return formatFixed(val, 2);
  }
  if (metricKey === "pause_time_sec") return formatFixed(val, 2);
  if (metricKey === "peak_elbow_ang_vel_deg_s") {
    if (val <= 0) return "\u2014";
    return `${formatFixed(val, 0)} \u00b0/s`;
  }
  if (metricKey === "elbow_angle_mean_deg") return formatFixed(val, 1);
  if (metricKey === "tremor_8_12hz_power") {
    if (om.tremor_abs_rms_px != null || om.tremor_present === false) {
      return formatTremorAmplitude(om.tremor_abs_rms_px, om.shoulder_width_px, om.tremor_present);
    }
    return formatTremorPower(val);
  }
  if (metricKey === "tremor_peak_freq_hz") {
    if (Number.isNaN(val)) return "\u2014";
    return `${val.toFixed(1)} Hz`;
  }
  if (metricKey === "movement_quality_index") return formatFixed(val, 2);
  if (metricKey === "fine_motor_quality_index") {
    if (val <= 0) return "\u2014";
    return formatFixed(val, 0);
  }
  if (metricKey === "shoulder_elevation_palm_ratio" || metricKey === "shoulder_elevation_table_ratio" || metricKey === "shoulder_elevation_norm" || metricKey === "shoulder_vert_norm") {
    if (val <= 0) return "\u2014";
    return formatFixed(val, 3);
  }
  if (metricKey === "tremor_index") return formatFixed(val, 0);
  return formatFixed(val, 2);
}
