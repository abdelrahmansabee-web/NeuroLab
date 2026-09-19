/**
 * Sparse on-video marks that prove the UE clinic panel numbers.
 * Paint only — NVP dots with +1, palm trail, trunk Δx, shoulder-to-table column.
 */
import {
  nvpPeakIndicesFromRest,
  nvpPeakIndicesInWindow,
  overlayMovementWindow,
  overlayPauseSpeedThreshold,
  pathLandmarkXY,
  restPathStartIdx,
} from "./validationPanelMetrics";
import { addCupToSpan, tableYFromCup } from "./overlayCupTable";
import { isSeatedTableY } from "./overlayCreamTable";
import { clampTableUserMark } from "./overlayTableUserMark";

const PATH_MOVE = "rgba(248,250,252,0.78)";
const NVP_FILL = "#e0e7ff";
const NVP_STROKE = "rgba(129,140,248,0.95)";
const TRUNK = "rgba(250,204,21,0.92)";
const SHOULDER = "rgba(245,158,11,0.9)";

export function nvpPeakIndicesOnPath(peakFrames, startIdx, untilIdx) {
  return nvpPeakIndicesInWindow(peakFrames, startIdx, untilIdx);
}

export function classifyPalmPath(frames, startIdx, untilIdx, speedThreshold) {
  const pts = [];
  if (!frames?.length) return pts;
  const hi = Math.max(startIdx, Math.min(frames.length - 1, untilIdx));
  const lo = Math.max(0, Math.min(hi, startIdx));
  for (let i = lo; i <= hi; i += 1) {
    const palm = pathLandmarkXY(frames[i]);
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

export function restFrameIndex(overlayData, startIdx = null) {
  if (Number.isFinite(Number(startIdx))) return Number(startIdx);
  return overlayMovementWindow(overlayData).startIdx;
}

export function restShoulderNorm(overlayData, frames, startIdx = null) {
  const i = restFrameIndex(overlayData, startIdx);
  const sh = frames?.[i]?.shoulder;
  if (sh && sh[0] != null && sh[1] != null) return [Number(sh[0]), Number(sh[1])];
  const frozen = overlayData?.table_under_shoulder;
  if (frozen && frozen.x != null && Number.isFinite(Number(frozen.x))) {
    const anc = overlayData?.shoulder_palm_anchor;
    const y = anc && Array.isArray(anc) && anc[1] != null ? Number(anc[1]) : Number(frozen.y);
    return [Number(frozen.x), y];
  }
  const anc = overlayData?.shoulder_palm_anchor;
  if (Array.isArray(anc) && anc[0] != null) return [Number(anc[0]), anc[1] != null ? Number(anc[1]) : null];
  if (anc && typeof anc === "object" && anc.x != null) return [Number(anc.x), anc.y != null ? Number(anc.y) : null];
  return null;
}

export function restPalmNorm(overlayData, frames, startIdx = null) {
  const i = restFrameIndex(overlayData, startIdx);
  const fp = frames?.[i]?.palm;
  if (fp && fp[1] != null && Number.isFinite(Number(fp[1]))) return [Number(fp[0]), Number(fp[1])];
  const p = overlayData?.start_palm;
  if (p && p[1] != null && Number.isFinite(Number(p[1]))) return [Number(p[0]), Number(p[1])];
  return null;
}

function finiteXY(p) {
  if (!p || p[0] == null || p[1] == null) return null;
  if (!Number.isFinite(Number(p[0])) || !Number.isFinite(Number(p[1]))) return null;
  return [Number(p[0]), Number(p[1])];
}

/** Shoulder of the arm that is on the table (closer to the rest palm). */
export function tableArmShoulderNorm(overlayData, frames, startIdx = null) {
  const i0 = restFrameIndex(overlayData, startIdx);
  const f = frames?.[i0];
  const palm = finiteXY(f?.palm) || finiteXY(overlayData?.start_palm);
  const l = finiteXY(f?.lshoulder);
  const r = finiteXY(f?.rshoulder);
  if (palm && l && r) {
    return Math.abs(l[0] - palm[0]) <= Math.abs(r[0] - palm[0]) ? l : r;
  }
  return restShoulderNorm(overlayData, frames, i0);
}

/**
 * Table surface Y: the supporting plane under the resting arm.
 * A person sees the table where the hand/wrist lie, not a chest-high edge.
 */
export function armOnTableY(overlayData, frames, startIdx = null, idx = null) {
  const i0 = restFrameIndex(overlayData, startIdx);
  const sh = restShoulderNorm(overlayData, frames, i0);
  const minY = sh && sh[1] != null && Number.isFinite(Number(sh[1]))
    ? Math.max(0.50, Number(sh[1]) + 0.10)
    : 0.50;
  const ys = [];
  const take = (p) => {
    if (!p || p[1] == null || !Number.isFinite(Number(p[1]))) return;
    const y = Number(p[1]);
    if (y >= minY) ys.push(y);
  };
  const fromFrame = (f) => {
    if (!f) return;
    take(f.palm);
    take(f.wrist);
    take(f.hl_wrist);
    take(f.elbow);
  };
  if (frames?.length) {
    const a = Math.max(0, i0 - 1);
    const b = Math.min(frames.length - 1, i0 + 8);
    for (let i = a; i <= b; i += 1) fromFrame(frames[i]);
    if (idx != null && Number.isFinite(Number(idx))) {
      const i = Math.max(0, Math.min(frames.length - 1, Number(idx)));
      fromFrame(frames[i]);
    }
  }
  take(overlayData?.start_palm);
  if (!ys.length) return null;
  const y = Math.max(...ys);
  return isSeatedTableY(y) ? y : null;
}

/** Horizontal span of the table under the arm (palm…elbow…trunk), not the chair. */
export function tableSpanX(overlayData, frames, startIdx = null, cup = null) {
  const i0 = restFrameIndex(overlayData, startIdx);
  const f = frames?.[i0] || {};
  const xs = [];
  const add = (p) => {
    if (p && p[0] != null && Number.isFinite(Number(p[0]))) xs.push(Number(p[0]));
  };
  add(f.palm);
  add(overlayData?.start_palm);
  add(f.wrist);
  add(f.hl_wrist);
  add(f.elbow);
  add(f.trunk);
  const armSh = tableArmShoulderNorm(overlayData, frames, i0);
  add(armSh);
  const span = xs.length ? { lo: Math.min(...xs) - 0.04, hi: Math.max(...xs) + 0.04 } : null;
  return addCupToSpan(span, cup || overlayData?.cup);
}

/**
 * Resting hand sits on the table. Reject a "table" edge that is still on the
 * chest / far wall (too high) or the front lip / floor (too low).
 */
export function snapTableYToRestArm(tableY, restPalmY, restShoulderY = null) {
  if (restPalmY == null || !Number.isFinite(Number(restPalmY))) {
    return tableY != null && Number.isFinite(Number(tableY)) ? Number(tableY) : null;
  }
  const palmY = Number(restPalmY);
  if (tableY == null || !Number.isFinite(Number(tableY))) return palmY;
  const ty = Number(tableY);
  if (ty < palmY - 0.06) return palmY;
  if (restShoulderY != null && Number.isFinite(Number(restShoulderY)) && ty < Number(restShoulderY) + 0.10) {
    return palmY;
  }
  if (ty > palmY + 0.12) return palmY;
  return ty;
}

/** Sample table-surface y (0–1) at a normalized x, using the per-column edge when present. */
export function tableSurfaceYAtX(overlayData, xNorm) {
  const frozen = overlayData?.table_under_shoulder;
  if (frozen && frozen.y != null && Number.isFinite(Number(frozen.y))) {
    if (xNorm == null || frozen.x == null || Math.abs(Number(xNorm) - Number(frozen.x)) < 0.08) {
      return Number(frozen.y);
    }
  }
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

export function tableRestXNorm(overlayData, shoulderCanvas, cw, frames = null, startIdx = null) {
  const frozen = overlayData?.table_under_shoulder;
  if (frozen && frozen.x != null && Number.isFinite(Number(frozen.x))) return Number(frozen.x);
  const rest = restShoulderNorm(overlayData, frames, startIdx);
  if (rest && Number.isFinite(rest[0])) return rest[0];
  const anc = overlayData?.shoulder_palm_anchor;
  if (Array.isArray(anc) && anc[0] != null && Number.isFinite(Number(anc[0]))) return Number(anc[0]);
  if (anc && typeof anc === "object" && anc.x != null && Number.isFinite(Number(anc.x))) return Number(anc.x);
  if (shoulderCanvas && cw > 0 && Number.isFinite(shoulderCanvas[0])) return shoulderCanvas[0] / cw;
  return null;
}

/**
 * During drink, pose often drops the affected shoulder (hand covers it).
 * Keep the height mark on the girdle: never follow that downward jump.
 */
export function robustShoulderNorm(overlayData, frames, idx, startIdx = null) {
  const i0 = restFrameIndex(overlayData, startIdx);
  const rest = frames?.[i0]?.shoulder;
  const cur = frames?.[idx]?.shoulder;
  if (!cur || cur[0] == null || cur[1] == null) return rest || null;
  let y = Number(cur[1]);
  const side = String(overlayData?.affected_side || "").toLowerCase();
  const contraKey = side === "left" ? "rshoulder" : "lshoulder";
  const restContra = frames?.[i0]?.[contraKey];
  const curContra = frames?.[idx]?.[contraKey];
  if (
    rest && rest[1] != null
    && restContra && restContra[1] != null
    && curContra && curContra[1] != null
  ) {
    const expected = Number(curContra[1]) + (Number(rest[1]) - Number(restContra[1]));
    y = Math.min(y, expected + 0.02);
  }
  const restPalm = restPalmNorm(overlayData, frames, i0);
  const curPalm = frames?.[idx]?.palm;
  const palmRaised = restPalm && curPalm && curPalm[1] != null && Number(curPalm[1]) < restPalm[1] - 0.07;
  if (palmRaised && rest && rest[1] != null) {
    y = Math.min(y, Number(rest[1]) + 0.015);
  }
  return [Number(cur[0]), y];
}

/** Table point on the supporting surface, under the affected shoulder. */
export function tablePointUnderShoulder(overlayData, frames, startIdx = null, idx = null, cup = null, userMark = null, creamY = null, hintY = null) {
  const user = clampTableUserMark(userMark || overlayData?.table_user);
  if (user) return { x: user.x, y: user.y };

  const i0 = restFrameIndex(overlayData, startIdx);
  const restSh = restShoulderNorm(overlayData, frames, i0);
  const armSh = tableArmShoulderNorm(overlayData, frames, i0);
  const restPalm = restPalmNorm(overlayData, frames, i0);
  const armY = armOnTableY(overlayData, frames, i0, idx);
  const c = cup || overlayData?.cup || null;
  const frozen = overlayData?.table_under_shoulder;

  let x = restSh?.[0] ?? armSh?.[0] ?? restPalm?.[0] ?? null;
  if (x == null && frozen && frozen.x != null && Number.isFinite(Number(frozen.x))) {
    x = Number(frozen.x);
  }

  const cream = Number(creamY ?? overlayData?.cream_table_y);
  const hint = Number(hintY ?? overlayData?.table_y_hint);
  const frozenY = frozen && frozen.y != null ? Number(frozen.y) : null;
  const cupY = tableYFromCup(c, isSeatedTableY(armY) ? armY : null);

  let y = null;
  if (isSeatedTableY(cream)) y = cream;
  else if (isSeatedTableY(cupY)) y = cupY;
  else if (isSeatedTableY(hint)) y = hint;
  else if (isSeatedTableY(frozenY)) y = frozenY;
  else if (isSeatedTableY(armY)) y = armY;
  else {
    y = snapTableYToRestArm(
      isSeatedTableY(tableSurfaceYAtX(overlayData, x)) ? tableSurfaceYAtX(overlayData, x) : null,
      restPalm?.[1],
      restSh?.[1],
    );
    if (!isSeatedTableY(y)) y = isSeatedTableY(armY) ? armY : null;
  }
  if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

/** Short table segment in overlay pixels, under the rest shoulder (frozen x/y). */
export function tableLineUnderShoulder(overlayData, {
  shoulder,
  cw,
  ch,
  shoulderWidthPx = 0,
  frames = null,
  startIdx = null,
  idx = null,
  cup = null,
  userMark = null,
  creamY = null,
  hintY = null,
} = {}) {
  if (!cw || !ch) return null;
  const pt = tablePointUnderShoulder(overlayData, frames, startIdx, idx, cup, userMark, creamY, hintY);
  if (!pt) return null;
  const robust = frames && idx != null
    ? robustShoulderNorm(overlayData, frames, idx, startIdx)
    : null;
  const liveX = shoulder && Number.isFinite(Number(shoulder[0])) ? Number(shoulder[0]) : null;
  const liveY = shoulder && Number.isFinite(Number(shoulder[1])) ? Number(shoulder[1]) : null;
  const userSet = Boolean(clampTableUserMark(userMark || overlayData?.table_user));
  const tableX = userSet ? pt.x * cw : (liveX != null ? liveX : pt.x * cw);
  const tableY = pt.y * ch;
  const colX = liveX != null ? liveX : tableX;
  const yTop = liveY != null
    ? liveY
    : (robust && Number.isFinite(robust[1]) ? robust[1] * ch : null);
  const half = Math.max(
    22,
    Math.min(cw * 0.07, shoulderWidthPx > 8 ? shoulderWidthPx * 0.32 : cw * 0.05),
  );
  return {
    x0: Math.max(2, tableX - half),
    x1: Math.min(cw - 2, tableX + half),
    x: tableX,
    colX,
    y: tableY,
    yNorm: pt.y,
    xNorm: tableX / cw,
    yTop,
  };
}

export function drawTableSurfaceLine(ctx, overlayData, opts = {}) {
  const cup = opts.cup || overlayData?.cup || null;
  const userMark = opts.userMark || overlayData?.table_user || null;
  const placing = Boolean(opts.placing);
  const g = tableLineUnderShoulder(overlayData, { ...opts, cup, userMark });
  if (!ctx || !g) return null;
  const { noShadow = false, cw, ch } = opts;
  const userSet = Boolean(clampTableUserMark(userMark));
  ctx.save();
  ctx.strokeStyle = "rgba(245,158,11,0.92)";
  ctx.fillStyle = "rgba(245,158,11,0.95)";
  ctx.lineWidth = placing || userSet ? 2.6 : 2.2;
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
  ctx.beginPath();
  ctx.arc(g.x, g.y, placing || userSet ? 6.2 : 4.4, 0, Math.PI * 2);
  ctx.fill();
  if (placing) {
    ctx.shadowBlur = 0;
    ctx.strokeStyle = "rgba(253,230,138,0.95)";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.arc(g.x, g.y, 10, 0, Math.PI * 2);
    ctx.stroke();
  }
  if (
    !userSet
    && cup
    && cup.x != null && cup.y_base != null
    && Number.isFinite(Number(cup.x)) && Number.isFinite(Number(cup.y_base))
    && cw > 0 && ch > 0
  ) {
    ctx.shadowBlur = 0;
    ctx.strokeStyle = "rgba(186,230,253,0.92)";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.arc(Number(cup.x) * cw, Number(cup.y_base) * ch, 5.2, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
  return g;
}

/** Table line under the shoulder, else palm-rest / start-palm y (normalized). */
export function resolveShoulderRestY(overlayData, frames, startIdx, xNorm = null) {
  const pt = tablePointUnderShoulder(
    overlayData,
    frames,
    startIdx,
    null,
    overlayData?.cup,
    overlayData?.table_user,
  );
  if (pt) return pt.y;
  const armY = armOnTableY(overlayData, frames, startIdx);
  if (armY != null) return armY;
  const fromTable = snapTableYToRestArm(
    tableSurfaceYAtX(overlayData, xNorm),
    restPalmNorm(overlayData, frames, startIdx)?.[1],
    restShoulderNorm(overlayData, frames, startIdx)?.[1],
  );
  if (fromTable != null) return fromTable;
  const rest = restPalmNorm(overlayData, frames, startIdx);
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
 * Draw NVP dots, palm trail, trunk dx arrow, and shoulder-to-table column. No extra text.
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
  const restIdx = restPathStartIdx(overlayData);
  if (idx < restIdx) return;
  const untilIdx = Math.max(restIdx, Math.min(idx, endIdx));
  const thresh = overlayPauseSpeedThreshold(frames);
  const pathPts = classifyPalmPath(frames, restIdx, untilIdx, thresh);

  ctx.save();
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  if (noShadow) {
    ctx.shadowBlur = 0;
    ctx.shadowColor = "transparent";
  }

  // Palm trail (average-velocity path) — one style, no pause encoding.
  ctx.globalAlpha = 0.82;
  ctx.lineWidth = 2.1;
  ctx.strokeStyle = PATH_MOVE;
  ctx.setLineDash([]);
  ctx.beginPath();
  let started = false;
  for (let k = 0; k < pathPts.length; k += 1) {
    const p = toCanvas(pathPts[k].palm, cw, ch);
    if (!p) continue;
    if (!started) {
      ctx.moveTo(p[0], p[1]);
      started = true;
    } else {
      ctx.lineTo(p[0], p[1]);
    }
  }
  if (started) ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;

  // NVP: one small dot per peak_frame up to now, with +1 as each peak appears.
  const peaks = nvpPeakIndicesFromRest(overlayData, untilIdx);
  for (let n = 0; n < peaks.length; n += 1) {
    const p = toCanvas(pathLandmarkXY(frames[peaks[n]]), cw, ch);
    if (!p) continue;
    ctx.beginPath();
    ctx.arc(p[0], p[1], 3.1, 0, Math.PI * 2);
    ctx.fillStyle = NVP_FILL;
    ctx.fill();
    ctx.strokeStyle = NVP_STROKE;
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.save();
    ctx.font = "bold 13px sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.lineWidth = 3;
    ctx.strokeStyle = NVP_STROKE;
    ctx.fillStyle = NVP_FILL;
    ctx.strokeText("+1", p[0] + 6, p[1] - 4);
    ctx.fillText("+1", p[0] + 6, p[1] - 4);
    ctx.restore();
  }

  // Current hand tick (wrist rest-landmark path end, not index tip).
  const pathEnd = toCanvas(pathLandmarkXY(frames[untilIdx]), cw, ch);
  if (pathEnd) {
    ctx.beginPath();
    ctx.arc(pathEnd[0], pathEnd[1], 3, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
  }

  // Trunk: short horizontal arrow = |Δx| at the trunk (away from the palm path).
  const trunkDisp = trunkHorizontalDispNorm(frames, startIdx, untilIdx);
  if (trunkDisp && Math.abs(trunkDisp.dx) * cw >= 3) {
    const ty = (trunk ? trunk[1] : trunkDisp.y * ch) + 12;
    const x0 = trunkDisp.startX * cw;
    const x1 = trunkDisp.endX * cw;
    const y = Math.max(8, Math.min(ch - 8, ty));
    drawHArrow(ctx, x0, x1, y, TRUNK);
  }

  // Shoulder: column glued to the live skeleton shoulder landmark,
  // down to the frozen table plane (gold mark Y).
  const tableLine = tableLineUnderShoulder(overlayData, {
    shoulder,
    cw,
    ch,
    frames,
    startIdx,
    idx,
    shoulderWidthPx: Number(overlayData?.shoulder_width_px) || 0,
    userMark: overlayData?.table_user,
  });
  const restY = tableLine?.yNorm ?? resolveShoulderRestY(
    overlayData,
    frames,
    startIdx,
    tableRestXNorm(overlayData, shoulder, cw, frames, startIdx),
  );
  const colX = (shoulder && Number.isFinite(shoulder[0])) ? shoulder[0] : tableLine?.colX;
  const y0 = (shoulder && Number.isFinite(shoulder[1])) ? shoulder[1] : tableLine?.yTop;
  if (colX != null && y0 != null && restY != null) {
    const y1 = restY * ch;
    if (Math.abs(y1 - y0) >= 4) {
      ctx.strokeStyle = SHOULDER;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.88;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(colX, y0);
      ctx.lineTo(colX, y1);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  ctx.restore();
}
