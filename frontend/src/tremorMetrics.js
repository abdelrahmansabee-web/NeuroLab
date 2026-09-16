/** 8–12 Hz tremor metrics — JS port of R an/motion_invariants.py (validation parity). */

export const TREMOR_BAND_HZ = [8.0, 12.0];
export const TREMOR_MIN_DURATION_S = 0.75;
export const TREMOR_INDEX_SCALE = 6.0;
/** Camera/MediaPipe jitter in the 8–12 Hz band is typically < 2 px RMS. */
export const TREMOR_NOISE_FLOOR_PX = 2;
export const TREMOR_PEAK_SNR = 2.5;

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
export function tremorPeakFreqHz(
  signal,
  fs,
  fLo = TREMOR_BAND_HZ[0],
  fHi = TREMOR_BAND_HZ[1],
  minDurationS = TREMOR_MIN_DURATION_S,
  { requireSnr = true } = {},
) {
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
  const bandPowers = [];
  for (let k = 1; k < spec.length; k += 1) {
    const freq = (k * fs) / y.length;
    if (freq < lo || freq > hi) continue;
    bandPowers.push(spec[k]);
    if (spec[k] > peakPower) {
      peakPower = spec[k];
      peakFreq = freq;
    }
  }
  if (peakFreq == null || peakPower <= 1e-12) return null;
  if (requireSnr && bandPowers.length >= 3) {
    const sorted = bandPowers.slice().sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)] || 0;
    if (peakPower < TREMOR_PEAK_SNR * Math.max(median, 1e-12)) return null;
  }
  return peakFreq;
}

export function tremorNoiseFloorPx(shoulderWidthPx = 0) {
  const sw = Number(shoulderWidthPx);
  const fromSw = Number.isFinite(sw) && sw > 0 ? 0.004 * sw : 0;
  return Math.max(TREMOR_NOISE_FLOOR_PX, fromSw);
}

function seriesLooksLikePixels(px, py) {
  let maxAbs = 0;
  const n = Math.min(px.length, py.length);
  for (let i = 0; i < n; i += 1) {
    const ax = Math.abs(Number(px[i]) || 0);
    const ay = Math.abs(Number(py[i]) || 0);
    if (ax > maxAbs) maxAbs = ax;
    if (ay > maxAbs) maxAbs = ay;
  }
  return maxAbs > 2;
}

/** RMS of 8–12 Hz palm displacement in video pixels (true amplitude, not relative %). */
export function tremorBandAbsRmsPx(pxNorm, pyNorm, fs, frameW, frameH, minDurationS = TREMOR_MIN_DURATION_S) {
  if (!pxNorm?.length || !pyNorm?.length || !(fs > 0)) return null;
  const n = Math.min(pxNorm.length, pyNorm.length);
  if (n < Math.max(16, Math.round(minDurationS * fs))) return null;
  const alreadyPx = seriesLooksLikePixels(pxNorm, pyNorm);
  const sx = alreadyPx ? 1 : Number(frameW) || 0;
  const sy = alreadyPx ? 1 : Number(frameH) || 0;
  if (!(sx > 0) || !(sy > 0)) return null;
  const x = linearDetrend(pxNorm.slice(0, n).map((v) => Number(v) || 0));
  const y = linearDetrend(pyNorm.slice(0, n).map((v) => Number(v) || 0));
  const bx = bandpassZeroPhase(x, fs);
  const by = bandpassZeroPhase(y, fs);
  const pad = Math.min(Math.max(4, Math.round(fs * 0.12)), Math.floor(n / 5));
  let ss = 0;
  let count = 0;
  for (let i = pad; i < n - pad; i += 1) {
    const dx = bx[i] * sx;
    const dy = by[i] * sy;
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) continue;
    ss += dx * dx + dy * dy;
    count += 1;
  }
  if (count < 8) return null;
  return Math.sqrt(ss / count);
}

function peakHzFromPalm(px, py, fps) {
  const n = Math.min(px.length, py.length);
  if (n < 8) return tremorPeakFreqHz(px, fps);
  let vx = 0;
  let vy = 0;
  for (let i = 0; i < n; i += 1) {
    vx += (Number(px[i]) || 0) ** 2;
    vy += (Number(py[i]) || 0) ** 2;
  }
  return tremorPeakFreqHz(vx >= vy ? px : py, fps);
}

export function tremorIsPresent(absRmsPx, shoulderWidthPx = 0) {
  if (absRmsPx == null || !Number.isFinite(absRmsPx)) return false;
  return absRmsPx >= tremorNoiseFloorPx(shoulderWidthPx);
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

function palmSeries(frames, startIdx, endIdx) {
  const px = [];
  const py = [];
  for (let i = startIdx; i <= endIdx && i < frames.length; i += 1) {
    const p = frames[i]?.palm;
    px.push(p && Number.isFinite(Number(p[0])) ? Number(p[0]) : 0);
    py.push(p && Number.isFinite(Number(p[1])) ? Number(p[1]) : 0);
  }
  return { px, py };
}

function gatedTremorOut(handPower, peakHz, absRmsPx, shoulderWidthPx) {
  const measured = absRmsPx != null && Number.isFinite(absRmsPx);
  const absRounded = measured ? Math.round(absRmsPx * 1000) / 1000 : null;
  const sw = Number(shoulderWidthPx);
  const absSw = absRounded != null && Number.isFinite(sw) && sw > 0
    ? Math.round((absRounded / sw) * 1e6) / 1e6
    : null;
  if (measured && !tremorIsPresent(absRmsPx, shoulderWidthPx)) {
    return {
      tremor_8_12hz_power: 0,
      hand_speed_tremor_8_12hz_power: 0,
      tremor_index: 100,
      tremor_peak_freq_hz: null,
      tremor_abs_rms_px: absRounded,
      tremor_abs_rms_sw: absSw,
      tremor_present: false,
    };
  }
  const out = {
    tremor_present: measured ? true : null,
    tremor_abs_rms_px: absRounded,
    tremor_abs_rms_sw: absSw,
  };
  if (handPower != null) {
    out.tremor_8_12hz_power = Math.round(handPower * 10000) / 10000;
    out.hand_speed_tremor_8_12hz_power = out.tremor_8_12hz_power;
    out.tremor_index = tremorIndexFromPower(handPower);
  }
  if (peakHz != null) out.tremor_peak_freq_hz = Math.round(peakHz * 100) / 100;
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
  const frameW = Number(overlayData.frame_width_px) || 0;
  const frameH = Number(overlayData.frame_height_px) || 0;

  const handSpeeds = segmentSpeeds(frames, startIdx, endIdx, true).map((v) => v / norm);
  const handPower = tremorBandPower(handSpeeds, fps);
  const { px, py } = palmSeries(frames, startIdx, endIdx);
  const peakHz = peakHzFromPalm(px, py, fps);
  const absRmsPx = tremorBandAbsRmsPx(px, py, fps, frameW, frameH);

  const out = gatedTremorOut(handPower, peakHz, absRmsPx, sw);

  const elbowAngles = angularVelocitySeries(frames, startIdx, endIdx, "elbow_angle");
  const elbowVel = gradientSpeed(elbowAngles, fps);
  const elbowPower = tremorBandPower(elbowVel, fps);
  if (out.tremor_present && elbowPower != null) {
    out.elbow_tremor_8_12hz_power = Math.round(elbowPower * 10000) / 10000;
  }
  return Object.keys(out).length ? out : null;
}

/** Cumulative tremor from movement start → currentIdx (live panel). */
export function computeLiveTremorPower(frames, fps, startIdx, currentIdx, shoulderWidthPx = 0, overlayData = null) {
  if (!frames?.length || currentIdx < startIdx) return null;
  const endIdx = Math.min(currentIdx, frames.length - 1);
  const sw = shoulderWidthPx > 0 ? shoulderWidthPx : 1;
  const speeds = segmentSpeeds(frames, startIdx, endIdx, true).map((v) => v / sw);
  const power = tremorBandPower(speeds, fps);
  const { px, py } = palmSeries(frames, startIdx, endIdx);
  const peakHz = peakHzFromPalm(px, py, fps);
  const frameW = Number(overlayData?.frame_width_px) || 0;
  const frameH = Number(overlayData?.frame_height_px) || 0;
  const absRmsPx = tremorBandAbsRmsPx(px, py, fps, frameW, frameH);
  return gatedTremorOut(power, peakHz, absRmsPx, shoulderWidthPx);
}

export function computeAdlTremorFromOverlay(overlayData) {
  const adl = overlayData?.adl_window;
  if (!adl || adl.start_idx == null || adl.end_idx == null) return null;
  return computeTremorFromOverlay(overlayData, {
    start_idx: adl.start_idx,
    end_idx: adl.end_idx,
  });
}

/** Prefer backend metric when within tolerance; else client recompute. Always apply the noise floor. */
export function resolveTremorMetrics(overlayData) {
  const backend = overlayData?.metrics || {};
  const computed = computeTremorFromOverlay(overlayData);
  const adlComputed = computeAdlTremorFromOverlay(overlayData);
  const out = { ...(computed || {}) };

  if (computed?.tremor_present === false) {
    out.tremor_8_12hz_power = 0;
    out.hand_speed_tremor_8_12hz_power = 0;
    out.tremor_index = 100;
    out.tremor_peak_freq_hz = null;
    out.index_tremor_8_12hz_power = 0;
    out.elbow_tremor_8_12hz_power = 0;
    out.adl_tremor_8_12hz_power = 0;
    out.tremor_present = false;
    return out;
  }

  const pick = (key) => {
    const b = backend[key];
    if (b != null && b !== "" && !Number.isNaN(Number(b))) {
      return Number(b);
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

  if (computed?.tremor_present === false || adlComputed?.tremor_present === false) {
    if (adlComputed?.tremor_present === false) out.adl_tremor_8_12hz_power = 0;
  }

  return out;
}

export function formatTremorPower(val) {
  if (val == null || Number.isNaN(val)) return "—";
  if (Number(val) === 0) return "0";
  return `${(Number(val) * 100).toFixed(1)}% rel`;
}

/** Absolute 8–12 Hz palm amplitude for the panel / overlay label. */
export function formatTremorAmplitude(absRmsPx, shoulderWidthPx = 0, present = undefined) {
  if (present === false) return "0";
  if (absRmsPx == null || !Number.isFinite(Number(absRmsPx))) return "—";
  const px = Number(absRmsPx);
  if (!tremorIsPresent(px, shoulderWidthPx)) return "0";
  const sw = Number(shoulderWidthPx);
  const pxTxt = `${px.toFixed(1)} px`;
  if (Number.isFinite(sw) && sw > 0) {
    return `${pxTxt} · ${((100 * px) / sw).toFixed(2)}% SW`;
  }
  return pxTxt;
}

export function formatTremorIndex(val) {
  if (val == null || Number.isNaN(val)) return "—";
  return Math.round(Number(val)).toString();
}

function rbjBandpass(fs, f0, Q) {
  const w0 = (2 * Math.PI * f0) / fs;
  const cos = Math.cos(w0);
  const sin = Math.sin(w0);
  const alpha = sin / (2 * Math.max(0.3, Q));
  const b0 = alpha;
  const b1 = 0;
  const b2 = -alpha;
  const a0 = 1 + alpha;
  const a1 = -2 * cos;
  const a2 = 1 - alpha;
  return {
    b0: b0 / a0,
    b1: b1 / a0,
    b2: b2 / a0,
    a1: a1 / a0,
    a2: a2 / a0,
  };
}

function biquadFilter(x, c) {
  const y = new Array(x.length);
  let z1 = 0;
  let z2 = 0;
  for (let i = 0; i < x.length; i += 1) {
    const v = x[i] - c.a1 * z1 - c.a2 * z2;
    y[i] = c.b0 * v + c.b1 * z1 + c.b2 * z2;
    z2 = z1;
    z1 = v;
  }
  return y;
}

/** Zero-phase 8–12 Hz bandpass for camera tremor visuals (same band as the FFT number). */
export function bandpassZeroPhase(y, fs, fLo = TREMOR_BAND_HZ[0], fHi = TREMOR_BAND_HZ[1]) {
  if (!y?.length || !(fs > 0)) return [];
  const nyq = fs * 0.5;
  const hi = Math.min(Number(fHi), nyq * 0.45);
  const lo = Math.max(Number(fLo), 1);
  if (!(hi > lo)) return y.map(() => 0);
  const f0 = 0.5 * (lo + hi);
  const Q = Math.max(0.6, f0 / Math.max(1, hi - lo));
  const c = rbjBandpass(fs, f0, Q);
  const x = y.map((v) => (Number.isFinite(v) ? Number(v) : 0));
  const fwd = biquadFilter(x, c);
  fwd.reverse();
  const back = biquadFilter(fwd, c);
  back.reverse();
  return back;
}

export function zeroCrossingHz(y, fs) {
  if (!y?.length || y.length < 6 || !(fs > 0)) return null;
  let xc = 0;
  for (let i = 1; i < y.length; i += 1) {
    const a = y[i - 1];
    const b = y[i];
    if (!Number.isFinite(a) || !Number.isFinite(b) || a === 0 || b === 0) continue;
    if ((a < 0 && b > 0) || (a > 0 && b < 0)) xc += 1;
  }
  const dur = (y.length - 1) / fs;
  if (dur < 0.15) return null;
  return xc / 2 / dur;
}

/**
 * Precompute camera 8–12 Hz residuals from overlay frames (no IMU).
 * `bandSpeed` is the same channel the panel FFT uses (`speed_tremor` / speed).
 */
export function buildTremorCameraTrack(overlayData) {
  const frames = overlayData?.frames;
  if (!frames?.length || frames.length < 16) return null;
  const fps = overlayData.fps || 60;
  const n = frames.length;
  const px = new Array(n);
  const py = new Array(n);
  const spd = new Array(n);
  for (let i = 0; i < n; i += 1) {
    const p = frames[i]?.palm;
    px[i] = p && Number.isFinite(Number(p[0])) ? Number(p[0]) : 0;
    py[i] = p && Number.isFinite(Number(p[1])) ? Number(p[1]) : 0;
    let s = frames[i]?.speed_tremor;
    if (s == null || Number.isNaN(Number(s))) s = frames[i]?.speed ?? 0;
    spd[i] = Number(s) || 0;
  }
  return {
    fps,
    n,
    dx: bandpassZeroPhase(px, fps),
    dy: bandpassZeroPhase(py, fps),
    speed: spd,
    bandSpeed: bandpassZeroPhase(spd, fps),
  };
}
