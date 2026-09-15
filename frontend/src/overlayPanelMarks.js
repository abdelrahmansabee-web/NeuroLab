/**
 * Sparse on-video marks that prove the UE panel numbers.
 * Paint only — uses the same palm / peak_frames / pause threshold as the panel.
 */
import { overlayMovementWindow, overlayPauseSpeedThreshold } from "./validationPanelMetrics";

const PATH_MOVE = "rgba(248,250,252,0.78)";
const PATH_PAUSE = "rgba(248,250,252,0.28)";
const CHORD = "rgba(34,211,238,0.82)";
const NVP_FILL = "#e0e7ff";
const NVP_STROKE = "rgba(129,140,248,0.95)";
const TRUNK = "rgba(250,204,21,0.92)";
const SHOULDER = "rgba(245,158,11,0.9)";

export function nvpPeakIndicesOnPath(peakFrames, startIdx, untilIdx) {
  return (peakFrames || []).filter(
    (pi) => Number.isFinite(Number(pi)) && pi >= startIdx && pi <= untilIdx,
  );
}

export function classifyPalmPath(frames, startIdx, untilIdx, speedThreshold) {
  const pts = [];
  if (!frames?.length) return pts;
  const hi = Math.max(startIdx, Math.min(frames.length - 1, untilIdx));
  const lo = Math.max(0, Math.min(hi, startIdx));
  for (let i = lo; i <= hi; i += 1) {
    const palm = frames[i]?.palm;
    if (!palm || palm[0] == null || palm[1] == null) continue;
    pts.push({
      i,
      palm,
      paused: (frames[i].speed || 0) < speedThreshold,
    });
  }
  return pts;
}

export function straightnessEndpoints(frames, startIdx, untilIdx) {
  const a = frames[startIdx]?.palm;
  const b = frames[untilIdx]?.palm;
  if (!a || !b || a[0] == null || b[0] == null) return null;
  return { start: a, end: b };
}

export function trunkHorizontalDispNorm(frames, startIdx, untilIdx) {
  const a = frames[startIdx]?.trunk;
  const b = frames[untilIdx]?.trunk;
  if (!a || !b || a[0] == null || b[0] == null) return null;
  return {
    startX: a[0],
    endX: b[0],
    y: b[1] != null ? b[1] : a[1],
    dx: b[0] - a[0],
  };
}

/** Sample table-surface y (0–1) at a normalized x, using the per-column edge when present. */
export function tableSurfaceYAtX(overlayData, xNorm) {
  const prof = overlayData?.table_edge_y;
  if (Array.isArray(prof) && prof.length >= 2 && xNorm != null && Number.isFinite(Number(xNorm))) {
    const n = prof.length;
    const t = Math.max(0, Math.min(1, Number(xNorm))) * (n - 1);
    const i0 = Math.max(0, Math.min(n - 1, Math.floor(t)));
    const i1 = Math.min(n - 1, i0 + 1);
    const a = Number(prof[i0]);
    const b = Number(prof[i1]);
    const f = t - i0;
    if (Number.isFinite(a) && Number.isFinite(b)) return a + (b - a) * f;
    if (Number.isFinite(a)) return a;
    if (Number.isFinite(b)) return b;
  }
  const ty = overlayData?.table_surface_y;
  if (ty != null && Number(ty) >= 0 && Number(ty) <= 1) return Number(ty);
  const anc = overlayData?.shoulder_palm_anchor;
  if (Array.isArray(anc) && anc[1] != null && Number.isFinite(Number(anc[1]))) return Number(anc[1]);
  if (anc && typeof anc === "object" && anc.y != null && Number.isFinite(Number(anc.y))) {
    return Number(anc.y);
  }
  return null;
}

export function tableRestXNorm(overlayData, shoulderCanvas, cw) {
  if (shoulderCanvas && cw > 0 && Number.isFinite(shoulderCanvas[0])) return shoulderCanvas[0] / cw;
  const anc = overlayData?.shoulder_palm_anchor;
  if (Array.isArray(anc) && anc[0] != null && Number.isFinite(Number(anc[0]))) return Number(anc[0]);
  if (anc && typeof anc === "object" && anc.x != null && Number.isFinite(Number(anc.x))) return Number(anc.x);
  return null;
}

/** Short table segment in overlay pixels, centered on the shoulder x. */
export function tableLineUnderShoulder(overlayData, { shoulder, cw, ch, shoulderWidthPx = 0 } = {}) {
  if (!cw || !ch) return null;
  const xNorm = tableRestXNorm(overlayData, shoulder, cw);
  const yNorm = tableSurfaceYAtX(overlayData, xNorm);
  if (yNorm == null || !Number.isFinite(yNorm)) return null;
  const x = shoulder && Number.isFinite(shoulder[0])
    ? shoulder[0]
    : (xNorm != null ? xNorm * cw : null);
  if (x == null || !Number.isFinite(x)) return null;
  const half = Math.max(
    26,
    Math.min(cw * 0.08, shoulderWidthPx > 8 ? shoulderWidthPx * 0.38 : cw * 0.055),
  );
  return {
    x0: Math.max(2, x - half),
    x1: Math.min(cw - 2, x + half),
    x,
    y: yNorm * ch,
    yNorm,
  };
}

export function drawTableSurfaceLine(ctx, overlayData, opts = {}) {
  const g = tableLineUnderShoulder(overlayData, opts);
  if (!ctx || !g) return null;
  const { noShadow = false } = opts;
  ctx.save();
  ctx.strokeStyle = "rgba(245,158,11,0.9)";
  ctx.lineWidth = 2.2;
  ctx.lineCap = "round";
  ctx.setLineDash([]);
  if (!noShadow) {
    ctx.shadowColor = "rgba(245,158,11,0.35)";
    ctx.shadowBlur = 6;
  }
  ctx.beginPath();
  ctx.moveTo(g.x0, g.y);
  ctx.lineTo(g.x1, g.y);
  ctx.stroke();
  ctx.restore();
  return g;
}

/** Table line under the shoulder, else palm-rest / start-palm y (normalized). */
export function resolveShoulderRestY(overlayData, frames, startIdx, xNorm = null) {
  const fromTable = tableSurfaceYAtX(overlayData, xNorm);
  if (fromTable != null) return fromTable;
  const rest = overlayData?.start_palm || frames?.[startIdx]?.palm;
  if (rest && rest[1] != null && Number.isFinite(Number(rest[1]))) return Number(rest[1]);
  return null;
}

function toCanvas(p, cw, ch) {
  if (!p || p[0] == null || p[1] == null) return null;
  return [p[0] * cw, p[1] * ch];
}

function drawHArrow(ctx, x0, x1, y, color) {
  const span = x1 - x0;
  if (!Number.isFinite(span) || Math.abs(span) < 3) return;
  const dir = span >= 0 ? 1 : -1;
  const head = Math.min(7, Math.abs(span) * 0.28);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1.8;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(x0, y);
  ctx.lineTo(x1, y);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x1, y);
  ctx.lineTo(x1 - dir * head, y - head * 0.55);
  ctx.lineTo(x1 - dir * head, y + head * 0.55);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

/**
 * Draw NVP dots, pause-styled palm path, straightness chord,
 * trunk dx arrow, and shoulder-to-table column. No extra text.
 */
export function drawPanelKinematicMarks(ctx, {
  overlayData,
  frames,
  idx,
  cw,
  ch,
  palm,
  trunk,
  shoulder,
  peakFrames,
  noShadow = false,
} = {}) {
  if (!ctx || !frames?.length || cw < 8 || ch < 8) return;
  const { startIdx, endIdx } = overlayMovementWindow(overlayData);
  if (idx < startIdx) return;
  const untilIdx = Math.max(startIdx, Math.min(idx, endIdx));
  const thresh = overlayPauseSpeedThreshold(frames);
  const pathPts = classifyPalmPath(frames, startIdx, untilIdx, thresh);

  ctx.save();
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  if (noShadow) {
    ctx.shadowBlur = 0;
    ctx.shadowColor = "transparent";
  }

  // 1. Straightness chord (behind the path).
  const chord = straightnessEndpoints(frames, startIdx, untilIdx);
  if (chord) {
    const a = toCanvas(chord.start, cw, ch);
    const b = toCanvas(chord.end, cw, ch);
    if (a && b && Math.hypot(b[0] - a[0], b[1] - a[1]) > 6) {
      ctx.strokeStyle = CHORD;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([7, 5]);
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // 2. Palm path: solid while moving, dashed+dim while paused.
  ctx.globalAlpha = 1;
  ctx.lineWidth = 2.1;
  for (let k = 1; k < pathPts.length; k += 1) {
    const a = toCanvas(pathPts[k - 1].palm, cw, ch);
    const b = toCanvas(pathPts[k].palm, cw, ch);
    if (!a || !b) continue;
    const paused = pathPts[k].paused;
    ctx.strokeStyle = paused ? PATH_PAUSE : PATH_MOVE;
    ctx.globalAlpha = paused ? 0.55 : 0.82;
    ctx.setLineDash(paused ? [3.5, 4.5] : []);
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;

  // 3. NVP: one small dot per peak_frame up to now on the path.
  const peaks = nvpPeakIndicesOnPath(peakFrames || overlayData?.peak_frames, startIdx, untilIdx);
  for (let n = 0; n < peaks.length; n += 1) {
    const p = toCanvas(frames[peaks[n]]?.palm, cw, ch);
    if (!p) continue;
    ctx.beginPath();
    ctx.arc(p[0], p[1], 3.1, 0, Math.PI * 2);
    ctx.fillStyle = NVP_FILL;
    ctx.fill();
    ctx.strokeStyle = NVP_STROKE;
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }

  // Tiny unlabeled start / current palm ticks (chord ends).
  if (chord) {
    const a = toCanvas(chord.start, cw, ch);
    const b = toCanvas(chord.end, cw, ch);
    if (a) {
      ctx.beginPath();
      ctx.arc(a[0], a[1], 3.4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(250,204,21,0.9)";
      ctx.fill();
    }
    if (b) {
      ctx.beginPath();
      ctx.arc(b[0], b[1], 3.4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.92)";
      ctx.fill();
      ctx.strokeStyle = "rgba(34,211,238,0.85)";
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
  } else if (palm) {
    ctx.beginPath();
    ctx.arc(palm[0], palm[1], 3, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
  }

  // 4. Trunk: short horizontal arrow = |Δx| at the trunk (away from the palm path).
  const trunkDisp = trunkHorizontalDispNorm(frames, startIdx, untilIdx);
  if (trunkDisp && Math.abs(trunkDisp.dx) * cw >= 3) {
    const ty = (trunk ? trunk[1] : trunkDisp.y * ch) + 12;
    const x0 = trunkDisp.startX * cw;
    const x1 = trunkDisp.endX * cw;
    const y = Math.max(8, Math.min(ch - 8, ty));
    drawHArrow(ctx, x0, x1, y, TRUNK);
  }

  // 5. Shoulder: column from shoulder down to the table line under that x.
  const tableLine = tableLineUnderShoulder(overlayData, {
    shoulder,
    cw,
    ch,
    shoulderWidthPx: Number(overlayData?.shoulder_width_px) || 0,
  });
  const restY = tableLine?.yNorm ?? resolveShoulderRestY(
    overlayData,
    frames,
    startIdx,
    tableRestXNorm(overlayData, shoulder, cw),
  );
  if (shoulder && restY != null) {
    const x = tableLine?.x ?? shoulder[0];
    const y0 = shoulder[1];
    const y1 = restY * ch;
    if (Math.abs(y1 - y0) >= 4) {
      ctx.strokeStyle = SHOULDER;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.88;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y1);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  ctx.restore();
}
