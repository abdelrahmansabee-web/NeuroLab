/**
 * One palm path for panel straightness and tremor.
 * Same samples as the cyan chord / white path on the validation video.
 */

function finitePair(p) {
  if (!p || p[0] == null || p[1] == null) return null;
  const x = Number(p[0]);
  const y = Number(p[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

/** Overlay palm x/y from startIdx through endIdx. Missing samples are NaN (not 0,0). */
export function overlayPalmPoints(frames, startIdx, endIdx) {
  const px = [];
  const py = [];
  if (!frames?.length) return { px, py };
  const lo = Math.max(0, Number(startIdx) || 0);
  const hi = Math.max(lo, Math.min(frames.length - 1, Number(endIdx)));
  for (let i = lo; i <= hi; i += 1) {
    const p = finitePair(frames[i]?.palm);
    px.push(p ? p[0] : NaN);
    py.push(p ? p[1] : NaN);
  }
  return { px, py };
}

/**
 * Displacement / pathLength on overlay palm — the live Straightness formula.
 * Consecutive missing samples are skipped, not jumped through the origin.
 */
export function overlayPalmPathStats(frames, startIdx, endIdx) {
  const { px, py } = overlayPalmPoints(frames, startIdx, endIdx);
  let pathLength = 0;
  let prevX = NaN;
  let prevY = NaN;
  for (let i = 0; i < px.length; i += 1) {
    if (Number.isFinite(px[i]) && Number.isFinite(py[i])) {
      if (Number.isFinite(prevX) && Number.isFinite(prevY)) {
        pathLength += Math.hypot(px[i] - prevX, py[i] - prevY);
      }
      prevX = px[i];
      prevY = py[i];
    }
  }
  const startP = finitePair(frames?.[Math.max(0, Number(startIdx) || 0)]?.palm);
  const endI = Math.max(0, Math.min((frames?.length || 1) - 1, Number(endIdx)));
  const endP = finitePair(frames?.[endI]?.palm);
  let displacement = 0;
  let straightness = 0;
  if (startP && endP && pathLength > 0) {
    displacement = Math.hypot(endP[0] - startP[0], endP[1] - startP[1]);
    straightness = Math.min(1, displacement / pathLength);
  }
  return {
    px,
    py,
    pathLength,
    displacement,
    straightness,
    startP,
    endP,
  };
}

/** Speed of the same segments that sum to pathLength (normalized units / sec). */
export function overlayPalmPathSpeeds(px, py, fps) {
  const n = Math.min(px.length, py.length);
  const out = new Array(n).fill(0);
  const dt = fps > 0 ? 1 / fps : 1;
  for (let i = 1; i < n; i += 1) {
    if (
      Number.isFinite(px[i]) && Number.isFinite(py[i])
      && Number.isFinite(px[i - 1]) && Number.isFinite(py[i - 1])
    ) {
      out[i] = Math.hypot(px[i] - px[i - 1], py[i] - py[i - 1]) / dt;
    }
  }
  if (n > 1) out[0] = out[1];
  return out;
}

/**
 * Overlay palm minus the straightness chord (start → end, timed along the window).
 * Slow reach/curve sits on the chord; leftover is the extra motion straightness sees.
 */
export function overlayPalmChordResidual(px, py) {
  const n = Math.min(px.length, py.length);
  const rx = new Array(n).fill(NaN);
  const ry = new Array(n).fill(NaN);
  if (n === 0) return { rx, ry };
  let i0 = 0;
  while (i0 < n && !(Number.isFinite(px[i0]) && Number.isFinite(py[i0]))) i0 += 1;
  let i1 = n - 1;
  while (i1 > i0 && !(Number.isFinite(px[i1]) && Number.isFinite(py[i1]))) i1 -= 1;
  if (i0 >= n || !Number.isFinite(px[i0])) return { rx, ry };
  const x0 = px[i0];
  const y0 = py[i0];
  const x1 = px[i1];
  const y1 = py[i1];
  const span = Math.max(1, i1 - i0);
  for (let i = 0; i < n; i += 1) {
    if (!Number.isFinite(px[i]) || !Number.isFinite(py[i])) continue;
    const t = (i - i0) / span;
    rx[i] = px[i] - (x0 + t * (x1 - x0));
    ry[i] = py[i] - (y0 + t * (y1 - y0));
  }
  return { rx, ry };
}
