/** Choose among stored overlay points. Does not invent a hand. */

export function overlayDist(a, b) {
  if (!a || !b) return Infinity;
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

export function pointNear(a, b, maxDist) {
  if (!a) return false;
  if (!b) return true;
  return overlayDist(a, b) <= maxDist;
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

export function shouldSnapSmooth(prev, next, minSide, jumpNorm = 0.12) {
  if (!prev || !next || !(minSide > 0)) return false;
  return overlayDist(prev, next) > jumpNorm * minSide;
}
