/** Choose among stored overlay points. Does not invent a hand. */

export const REST_STAY_NORM = 0.12;

export function overlayDist(a, b) {
  if (!a || !b) return Infinity;
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

export function pointNear(a, b, maxDist) {
  if (!a) return false;
  if (!b) return true;
  return overlayDist(a, b) <= maxDist;
}

export function centroid(points) {
  const pts = (points || []).filter(Boolean);
  if (!pts.length) return null;
  return [
    pts.reduce((s, p) => s + p[0], 0) / pts.length,
    pts.reduce((s, p) => s + p[1], 0) / pts.length,
  ];
}

export function splitMovedFromRest(points, restPt, minSide, restNorm = REST_STAY_NORM) {
  const restPx = restNorm * (minSide || 0);
  const moved = [];
  const stuck = [];
  for (const p of points || []) {
    if (!p) continue;
    if (restPt && minSide > 0 && overlayDist(p, restPt) <= restPx) stuck.push(p);
    else moved.push(p);
  }
  return { moved, stuck };
}

export function elbowOnArm(shoulder, elbow, hand, minSide) {
  if (!shoulder || !elbow || !hand) return Boolean(elbow);
  if (!(minSide > 0)) return true;
  const sh = overlayDist(shoulder, hand);
  const se = overlayDist(shoulder, elbow);
  const eh = overlayDist(elbow, hand);
  if (!(sh > 0)) return false;
  if (se + eh > sh + 0.10 * minSide) return false;
  if (se < 0.03 * minSide) return false;
  return true;
}

/**
 * Forearm end: Hand Landmarker wrist when it still continues the pose forearm.
 * If HL has jumped to the table or the other hand, keep the pose wrist.
 */
export function pickForearmEnd(elbow, poseWrist, hlWrist, minSide) {
  if (!(minSide > 0)) return poseWrist || hlWrist || null;
  if (!hlWrist) return poseWrist || null;
  if (!elbow) {
    if (!poseWrist) return hlWrist;
    return overlayDist(hlWrist, poseWrist) <= 0.22 * minSide ? hlWrist : poseWrist;
  }

  const hlLen = overlayDist(elbow, hlWrist);
  const poseLen = poseWrist ? overlayDist(elbow, poseWrist) : NaN;
  const maxForearm = Math.max(0.55 * minSide, (Number.isFinite(poseLen) ? poseLen : 0) * 1.85);
  const minForearm = 0.03 * minSide;
  if (hlLen < minForearm || hlLen > maxForearm) return poseWrist || null;
  if (!poseWrist) return hlWrist;

  const vx = poseWrist[0] - elbow[0];
  const vy = poseWrist[1] - elbow[1];
  const ux = hlWrist[0] - elbow[0];
  const uy = hlWrist[1] - elbow[1];
  const denom = (poseLen * hlLen) || 1;
  const cos = (vx * ux + vy * uy) / denom;
  if (cos < 0.35 && overlayDist(hlWrist, poseWrist) > 0.22 * minSide) {
    return poseWrist;
  }
  return hlWrist;
}

/**
 * After the reach leaves the rest pose, follow the stored point that left
 * the table — not the Hand Landmarker cluster that stayed put.
 */
export function pickMovingHandRoot({
  shoulder,
  elbow,
  poseWrist,
  hlWrist,
  palm,
  indexTip,
  movedCentroid,
  restPt,
  minSide,
} = {}) {
  if (!(minSide > 0)) {
    return movedCentroid || palm || indexTip || hlWrist || poseWrist || null;
  }
  const restPx = REST_STAY_NORM * minSide;
  const all = [movedCentroid, palm, indexTip, hlWrist, poseWrist].filter(Boolean);
  if (!all.length) return pickForearmEnd(elbow, poseWrist, hlWrist, minSide);

  const leftRest = restPt
    ? all.filter((p) => overlayDist(p, restPt) > restPx)
    : [];
  if (!leftRest.length) {
    return pickForearmEnd(elbow, poseWrist, hlWrist, minSide) || all[0];
  }

  const origin = shoulder || elbow;
  if (!origin) return leftRest[0];

  const maxArm = 0.78 * minSide;
  const minArm = 0.05 * minSide;
  let best = null;
  let bestLen = -1;
  for (const p of leftRest) {
    const len = overlayDist(origin, p);
    if (len < minArm || len > maxArm) continue;
    if (len > bestLen) {
      bestLen = len;
      best = p;
    }
  }
  return best || leftRest[0];
}

export function shouldSnapSmooth(prev, next, minSide, jumpNorm = 0.12) {
  if (!prev || !next || !(minSide > 0)) return false;
  return overlayDist(prev, next) > jumpNorm * minSide;
}
