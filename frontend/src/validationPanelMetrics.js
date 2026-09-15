/**
 * Single source of truth for UE validation-video panel numbers.
 * The kinematics table, overlay_metrics, and the live panel all read these formulas.
 */
import {
  computeLiveTremorPower,
  formatTremorPower,
  resolveTremorMetrics,
} from "./tremorMetrics";

/** Table / report keys that must copy the validation-video panel (not server SPSS fields). */
export const PANEL_TABLE_KEYS = [
  "nvp",
  "nvp_reach",
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
  const peakFrames = overlayData.peak_frames || [];
  const f = frames[idx] || {};

  const speedThreshold = overlayPauseSpeedThreshold(frames);
  const inMovement = idx >= startIdx && idx <= endIdx;
  const t0 = startIdx < frames.length ? (frames[startIdx].time || startIdx / fps) : 0;

  const nvp = peakFrames.filter((pi) => pi <= idx).length;

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

  let straightness = 0;
  if (inMovement) {
    let pathLength = 0;
    const startP = frames[startIdx]?.palm;
    for (let i = startIdx + 1; i <= idx && i < frames.length; i += 1) {
      const prev = frames[i - 1]?.palm;
      const curr = frames[i]?.palm;
      if (prev && curr) pathLength += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
    }
    const endP = frames[idx]?.palm;
    if (startP && endP && pathLength > 0) {
      const displacement = Math.hypot(endP[0] - startP[0], endP[1] - startP[1]);
      straightness = Math.min(1, displacement / pathLength);
    }
  }

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
  );
  let adlTremorLive = null;
  if (overlayData?.adl_window) {
    adlTremorLive = computeLiveTremorPower(
      frames,
      fps,
      overlayData.adl_window.start_idx ?? startIdx,
      Math.max(overlayData.adl_window.start_idx ?? startIdx, idx),
      overlayData?.shoulder_width_px || 0,
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
    ];
    for (const k of passthrough) {
      if (backend[k] != null && backend[k] !== "") out[k] = backend[k];
    }
  }

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
  if (metricKey === "nvp" || metricKey === "nvp_reach" || metricKey === "number_of_stops") return formatFixed(val, 0);
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
  if (metricKey === "tremor_8_12hz_power") return formatTremorPower(val);
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
