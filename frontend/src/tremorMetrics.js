/** 8–12 Hz tremor metrics — JS port of R an/motion_invariants.py (validation parity). */

export const TREMOR_BAND_HZ = [8.0, 12.0];
export const TREMOR_MIN_DURATION_S = 0.75;
export const TREMOR_INDEX_SCALE = 6.0;

function fillShortNanGaps(y, maxGap = 4) {
  const out = y.slice();
  const n = out.length;
  let i = 0;
  while (i < n) {
    if (Number.isFinite(out[i])) {
      i += 1;
      continue;
    }
    let j = i;
    while (j < n && !Number.isFinite(out[j])) j += 1;
    const gap = j - i;
    if (gap > 0 && gap <= maxGap) {
      const left = i > 0 && Number.isFinite(out[i - 1]) ? out[i - 1] : NaN;
      const right = j < n && Number.isFinite(out[j]) ? out[j] : NaN;
      if (Number.isFinite(left) && Number.isFinite(right)) {
        for (let k = 0; k < gap; k += 1) {
          out[i + k] = left + ((right - left) * (k + 1)) / (gap + 1);
        }
      } else if (Number.isFinite(left)) {
        for (let k = i; k < j; k += 1) out[k] = left;
      } else if (Number.isFinite(right)) {
        for (let k = i; k < j; k += 1) out[k] = right;
      }
    }
    i = j > i ? j : i + 1;
  }
  return out;
}

function linearDetrend(y) {
  const n = y.length;
  const t = Array.from({ length: n }, (_, i) => i);
  const ok = y.map((v) => Number.isFinite(v));
  const okCount = ok.filter(Boolean).length;
  if (okCount < Math.max(8, Math.floor(n / 4))) {
    const mu = y.filter(Number.isFinite).reduce((a, b) => a + b, 0) / Math.max(1, okCount);
    return y.map((v) => (Number.isFinite(v) ? v - mu : 0));
  }
  let sumT = 0;
  let sumY = 0;
  let sumTT = 0;
  let sumTY = 0;
  for (let i = 0; i < n; i += 1) {
    if (!ok[i]) continue;
    sumT += t[i];
    sumY += y[i];
    sumTT += t[i] * t[i];
    sumTY += t[i] * y[i];
  }
  const denom = okCount * sumTT - sumT * sumT;
  const slope = Math.abs(denom) > 1e-12 ? (okCount * sumTY - sumT * sumY) / denom : 0;
  const intercept = (sumY - slope * sumT) / okCount;
  return y.map((v, i) => (Number.isFinite(v) ? v - (intercept + slope * t[i]) : 0));
}

function hannWindow(n) {
  if (n <= 1) return [1];
  return Array.from({ length: n }, (_, i) => 0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1))));
}

function rfftPower(y) {
  const n = y.length;
  const half = Math.floor(n / 2) + 1;
  const spec = new Array(half).fill(0);
  for (let k = 0; k < half; k += 1) {
    let re = 0;
    let im = 0;
    for (let t = 0; t < n; t += 1) {
      const ang = (-2 * Math.PI * k * t) / n;
      re += y[t] * Math.cos(ang);
      im += y[t] * Math.sin(ang);
    }
    spec[k] = re * re + im * im;
  }
  return spec;
}

/** Relative 8–12 Hz power vs total above 1 Hz (matches backend tremor_band_power). */
export function tremorBandPower(signal, fs, fLo = TREMOR_BAND_HZ[0], fHi = TREMOR_BAND_HZ[1], minDurationS = TREMOR_MIN_DURATION_S) {
  if (!fs || fs <= 0 || !signal?.length) return null;
  let y = fillShortNanGaps(signal.map((v) => Number(v)));
  const minN = Math.max(16, Math.round(minDurationS * fs));
  if (y.length < minN) return null;
  y = linearDetrend(y).map((v) => (Number.isFinite(v) ? v : 0));
  const w = hannWindow(y.length);
  const yw = y.map((v, i) => v * w[i]);
  const spec = rfftPower(yw);
  const hi = Math.min(fHi, fs * 0.45);
  const lo = Math.max(fLo, 1.0);
  if (hi <= lo) return null;
  let total = 0;
  let band = 0;
  for (let k = 1; k < spec.length; k += 1) {
    const freq = (k * fs) / y.length;
    if (freq >= 1.0) total += spec[k];
    if (freq >= lo && freq <= hi) band += spec[k];
  }
  if (total <= 1e-12) return null;
  return band / total;
}

/** Dominant frequency (Hz) within 8–12 Hz band — matches backend tremor_peak_freq_hz. */
export function tremorPeakFreqHz(signal, fs, fLo = TREMOR_BAND_HZ[0], fHi = TREMOR_BAND_HZ[1], minDurationS = TREMOR_MIN_DURATION_S) {
  if (!fs || fs <= 0 || !signal?.length) return null;
  let y = fillShortNanGaps(signal.map((v) => Number(v)));
  const minN = Math.max(16, Math.round(minDurationS * fs));
  if (y.length < minN) return null;
  y = linearDetrend(y).map((v) => (Number.isFinite(v) ? v : 0));
  const w = hannWindow(y.length);
  const yw = y.map((v, i) => v * w[i]);
  const spec = rfftPower(yw);
  const hi = Math.min(fHi, fs * 0.45);
  const lo = Math.max(fLo, 1.0);
  if (hi <= lo) return null;
  let peakFreq = null;
  let peakPower = -1;
  for (let k = 1; k < spec.length; k += 1) {
    const freq = (k * fs) / y.length;
    if (freq < lo || freq > hi) continue;
    if (spec[k] > peakPower) {
      peakPower = spec[k];
      peakFreq = freq;
    }
  }
  return peakFreq;
}

export function tremorIndexFromPower(power) {
  if (power == null || !Number.isFinite(power)) return null;
  return Math.round(Math.max(0, Math.min(100, 100 * (1 - Math.min(1, power * TREMOR_INDEX_SCALE)))));
}

function segmentSpeeds(frames, startIdx, endIdx, useTremorChannel = true) {
  const seg = [];
  for (let i = startIdx; i <= endIdx && i < frames.length; i += 1) {
    const f = frames[i];
    let v = useTremorChannel ? f?.speed_tremor : f?.speed;
    if (v == null || Number.isNaN(v)) v = f?.speed ?? 0;
    seg.push(Number(v) || 0);
  }
  return seg;
}

function angularVelocitySeries(frames, startIdx, endIdx, angleKey) {
  const seg = [];
  for (let i = startIdx; i <= endIdx && i < frames.length; i += 1) {
    const a = frames[i]?.[angleKey];
    seg.push(a != null && !Number.isNaN(a) ? Number(a) : NaN);
  }
  return seg;
}

function gradientSpeed(values, fps) {
  if (values.length < 2) return [];
  const out = [];
  for (let i = 0; i < values.length; i += 1) {
    const i0 = Math.max(0, i - 1);
    const i1 = Math.min(values.length - 1, i + 1);
    const dt = Math.max(1e-6, (i1 - i0) / fps);
    out.push(Math.abs((values[i1] - values[i0]) / dt));
  }
  return out;
}

/** Full-window tremor from overlay frames (movement window). */
export function computeTremorFromOverlay(overlayData, windowOverride = null) {
  if (!overlayData?.frames?.length) return null;
  const frames = overlayData.frames;
  const fps = overlayData.fps || 60;
  const win = windowOverride || overlayData.movement_window || { start_idx: 0, end_idx: frames.length - 1 };
  const startIdx = Math.max(0, Math.min(frames.length - 1, win.start_idx || 0));
  const endIdx = Math.max(startIdx, Math.min(frames.length - 1, win.end_idx || frames.length - 1));
  const sw = Number(overlayData.shoulder_width_px) || 0;
  const norm = sw > 0 ? sw : 1;

  const handSpeeds = segmentSpeeds(frames, startIdx, endIdx, true).map((v) => v / norm);
  const handPower = tremorBandPower(handSpeeds, fps);

  const elbowAngles = angularVelocitySeries(frames, startIdx, endIdx, "elbow_angle");
  const elbowVel = gradientSpeed(elbowAngles, fps);
  const elbowPower = tremorBandPower(elbowVel, fps);

  const out = {};
  if (handPower != null) {
    out.tremor_8_12hz_power = Math.round(handPower * 10000) / 10000;
    out.hand_speed_tremor_8_12hz_power = out.tremor_8_12hz_power;
    out.tremor_index = tremorIndexFromPower(handPower);
    const peakHz = tremorPeakFreqHz(handSpeeds, fps);
    if (peakHz != null) out.tremor_peak_freq_hz = Math.round(peakHz * 100) / 100;
  }
  if (elbowPower != null) {
    out.elbow_tremor_8_12hz_power = Math.round(elbowPower * 10000) / 10000;
  }
  return Object.keys(out).length ? out : null;
}

/** Cumulative tremor from movement start → currentIdx (live panel). */
export function computeLiveTremorPower(frames, fps, startIdx, currentIdx, shoulderWidthPx = 0) {
  if (!frames?.length || currentIdx < startIdx) return null;
  const endIdx = Math.min(currentIdx, frames.length - 1);
  const sw = shoulderWidthPx > 0 ? shoulderWidthPx : 1;
  const speeds = segmentSpeeds(frames, startIdx, endIdx, true).map((v) => v / sw);
  const power = tremorBandPower(speeds, fps);
  if (power == null) return null;
  return {
    tremor_8_12hz_power: Math.round(power * 10000) / 10000,
    tremor_index: tremorIndexFromPower(power),
  };
}

export function computeAdlTremorFromOverlay(overlayData) {
  const adl = overlayData?.adl_window;
  if (!adl || adl.start_idx == null || adl.end_idx == null) return null;
  return computeTremorFromOverlay(overlayData, {
    start_idx: adl.start_idx,
    end_idx: adl.end_idx,
  });
}

/** Prefer backend metric when within tolerance; else client recompute. */
export function resolveTremorMetrics(overlayData) {
  const backend = overlayData?.metrics || {};
  const computed = computeTremorFromOverlay(overlayData);
  const adlComputed = computeAdlTremorFromOverlay(overlayData);
  const out = { ...(computed || {}) };

  const pick = (key) => {
    const b = backend[key];
    if (b != null && b !== "" && !Number.isNaN(Number(b))) {
      const bv = Number(b);
      const cv = out[key];
      if (cv == null || Math.abs(bv - cv) <= 0.002) return bv;
      return bv;
    }
    return out[key] ?? null;
  };

  out.tremor_8_12hz_power = pick("tremor_8_12hz_power");
  out.hand_speed_tremor_8_12hz_power = pick("hand_speed_tremor_8_12hz_power") ?? out.tremor_8_12hz_power;
  out.tremor_index = pick("tremor_index") ?? tremorIndexFromPower(out.tremor_8_12hz_power);
  out.tremor_peak_freq_hz = pick("tremor_peak_freq_hz") ?? out.tremor_peak_freq_hz ?? null;
  out.index_tremor_8_12hz_power = pick("index_tremor_8_12hz_power");
  out.elbow_tremor_8_12hz_power = pick("elbow_tremor_8_12hz_power");

  const adlBackend = backend.adl_tremor_8_12hz_power;
  if (adlBackend != null && adlBackend !== "" && !Number.isNaN(Number(adlBackend))) {
    out.adl_tremor_8_12hz_power = Number(adlBackend);
  } else if (adlComputed?.tremor_8_12hz_power != null) {
    out.adl_tremor_8_12hz_power = adlComputed.tremor_8_12hz_power;
  }

  return out;
}

export function formatTremorPower(val) {
  if (val == null || Number.isNaN(val)) return "—";
  return `${(Number(val) * 100).toFixed(1)}% rel`;
}

export function formatTremorIndex(val) {
  if (val == null || Number.isNaN(val)) return "—";
  return Math.round(Number(val)).toString();
}
