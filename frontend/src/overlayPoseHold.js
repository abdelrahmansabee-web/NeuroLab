/** Display-only hold: ignore MediaPipe jitter so rest stays still. Does not change overlay tracking math. */

export const OVERLAY_TRACKING_NOISE_PX = 2;

export function overlayTrackingNoisePx(frameWidthPx = 0, frameHeightPx = 0) {
  const minSide = Math.min(Number(frameWidthPx) || 0, Number(frameHeightPx) || 0);
  const fromFrame = minSide > 0 ? 0.002 * minSide : 0;
  return Math.max(OVERLAY_TRACKING_NOISE_PX, fromFrame);
}

export function resetHoldIfSeek(store, idx, jump = 8) {
  if (!store) return;
  if (store._idx != null && Math.abs(idx - store._idx) > jump) {
    Object.keys(store).forEach((k) => {
      delete store[k];
    });
  }
  store._idx = idx;
}

/** Canvas point from a 0–1 landmark, held until motion beats camera/MediaPipe noise. */
export function holdDisplayLandmark(store, key, blended, cw, ch, idx) {
  if (!blended) return null;
  resetHoldIfSeek(store, idx);
  const canvas = [Number(blended[0]) * cw, Number(blended[1]) * ch];
  if (!Number.isFinite(canvas[0]) || !Number.isFinite(canvas[1])) return null;
  return holdTrackingNoise(store, key, canvas, overlayTrackingNoisePx(cw, ch));
}

/** Keep last drawn point until canvas motion exceeds tracking noise. */
export function holdTrackingNoise(store, key, next, pxFloor = OVERLAY_TRACKING_NOISE_PX) {
  if (!next) return null;
  if (!store) return next;
  const prev = store[key];
  if (!prev) {
    store[key] = [next[0], next[1]];
    return store[key];
  }
  const d = Math.hypot(next[0] - prev[0], next[1] - prev[1]);
  if (d < pxFloor) return prev;
  store[key] = [next[0], next[1]];
  return store[key];
}
