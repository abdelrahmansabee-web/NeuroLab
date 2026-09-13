/**
 * Hand skeleton — MCP → PIP → DIP → TIP (3 phalanges + metacarpal segment).
 * Reference: hand_skeleton_anatomy.jpeg (T-pose clinical atlas).
 */

export const HAND_ANATOMY_REF = "hand_skeleton_anatomy.jpeg";

/** @type {Record<string, { mcp: number, pip: number, dip: number, tip: number, angle: number }>} */
export const HAND_FINGER_BONES = {
  thumb: { angle: -0.72, mcp: 0.032, pip: 0.024, dip: 0.020, tip: 0.018 },
  index: { angle: -0.20, mcp: 0.042, pip: 0.036, dip: 0.030, tip: 0.028 },
  middle: { angle: 0.0, mcp: 0.046, pip: 0.040, dip: 0.034, tip: 0.032 },
  ring: { angle: 0.18, mcp: 0.044, pip: 0.038, dip: 0.032, tip: 0.030 },
  pinky: { angle: 0.36, mcp: 0.038, pip: 0.032, dip: 0.028, tip: 0.024 },
};

export const HAND_FINGER_ORDER = ["thumb", "index", "middle", "ring", "pinky"];
export const HAND_MIN_TIP_SPREAD_NORM = 0.038;

export function fingerSegmentLengths(spec) {
  const mcp = spec.mcp;
  const pip = mcp + spec.pip;
  const dip = pip + spec.dip;
  const tip = dip + spec.tip;
  return { mcp, pip, dip, tip, total: tip };
}

export function handAxesFromElbowPalm(elbowNorm, palmNorm) {
  if (!elbowNorm || !palmNorm) return null;
  const [ex, ey] = elbowNorm;
  const [px, py] = palmNorm;
  if (ex == null || ey == null || px == null || py == null) return null;
  let fx = px - ex;
  let fy = py - ey;
  const fl = Math.hypot(fx, fy);
  if (fl < 1e-5) return null;
  fx /= fl;
  fy /= fl;
  return { fx, fy, px: -fy, py: fx };
}

function rotate(fx, fy, ang) {
  const c = Math.cos(ang);
  const s = Math.sin(ang);
  return [fx * c - fy * s, fx * s + fy * c];
}

function along(palm, dx, dy, dist, scale, offX = 0, offY = 0) {
  return [palm[0] + dx * dist * scale + offX, palm[1] + dy * dist * scale + offY];
}

export function buildAnatomyHandLandmarks(palmNorm, axes, scale = 1.0) {
  const out = {};
  for (const id of HAND_FINGER_ORDER) {
    const spec = HAND_FINGER_BONES[id];
    const [dx, dy] = rotate(axes.fx, axes.fy, spec.angle);
    const seg = fingerSegmentLengths(spec);
    const ox = axes.px * spec.angle * 0.012 * scale;
    const oy = axes.py * spec.angle * 0.012 * scale;
    out[id] = {
      mcp: along(palmNorm, dx, dy, seg.mcp, scale, ox, oy),
      pip: along(palmNorm, dx, dy, seg.pip, scale),
      dip: along(palmNorm, dx, dy, seg.dip, scale),
      tip: along(palmNorm, dx, dy, seg.tip, scale),
    };
  }
  return out;
}

export function resolveHandSkeleton(tracked, palmNorm, elbowNorm, { normIs01 = true, cw = 1, scale = 1.0, hlConf = 0 } = {}) {
  const axes = handAxesFromElbowPalm(elbowNorm, palmNorm);
  if (!axes || !palmNorm) return { source: "tracked", fingers: tracked, anatomy: null };

  const validTips = HAND_FINGER_ORDER.filter((id) => tracked[id] && tracked[id][0] != null).length;
  if (Number(hlConf) >= 0.48 && validTips >= 3) {
    return { source: "tracked", fingers: tracked, anatomy: null };
  }

  let maxSpread = 0;
  for (const id of HAND_FINGER_ORDER) {
    const p = tracked[id];
    if (!p || p[0] == null) continue;
    const tx = normIs01 ? p[0] : p[0] / cw;
    const ty = normIs01 ? p[1] : p[1] / cw;
    maxSpread = Math.max(maxSpread, Math.hypot(tx - palmNorm[0], ty - palmNorm[1]));
  }

  if (maxSpread >= HAND_MIN_TIP_SPREAD_NORM * 0.85) {
    return { source: "tracked", fingers: tracked, anatomy: null };
  }

  const anatomy = buildAnatomyHandLandmarks(palmNorm, axes, scale);
  const merged = { ...tracked };
  for (const id of HAND_FINGER_ORDER) {
    merged[id] = anatomy[id].tip;
    merged[`${id}_mcp`] = anatomy[id].mcp;
    merged[`${id}_pip`] = anatomy[id].pip;
    merged[`${id}_dip`] = anatomy[id].dip;
  }
  return { source: "anatomy", fingers: merged, anatomy };
}

export function estimateHandScale(palmNorm, tracked, shoulderWidthNorm) {
  if (shoulderWidthNorm && shoulderWidthNorm > 0) {
    return Math.min(1.25, Math.max(0.75, shoulderWidthNorm * 0.55));
  }
  const mid = tracked.middle || tracked.index;
  if (mid && palmNorm && mid[0] != null) {
    const d = Math.hypot(mid[0] - palmNorm[0], mid[1] - palmNorm[1]);
    if (d > 0.05) return Math.min(1.3, Math.max(0.8, d / 0.142));
  }
  return 1.0;
}
