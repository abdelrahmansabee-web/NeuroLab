/** Play from the start when the clip has ended (iOS stays on a black EOS frame otherwise). */
export function shouldRestartPlayback({ ended, currentTime, duration } = {}) {
  if (ended) return true;
  const dur = Number(duration);
  const t = Number(currentTime);
  if (!Number.isFinite(dur) || dur <= 0 || !Number.isFinite(t)) return false;
  return t >= dur - 0.12;
}

/** iPad/iPhone: copying a <video> into a canvas often detaches the video layer. */
export function isAppleTouchVideo() {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  if (/iPad|iPhone|iPod/i.test(ua)) return true;
  return navigator.platform === "MacIntel" && (navigator.maxTouchPoints || 0) > 1;
}

function overlayFrameTime(frames, idx, t0, fps) {
  const frame = frames[idx];
  if (!frame) return t0 + idx / fps;
  return frame.time ?? t0 + idx / fps;
}

/**
 * Map the presented video time to the overlay sample for that picture.
 * Snap to the nearest stored landmark frame (no blend toward the next sample) so
 * the skeleton is the pose computed for this video time, not a halfway pose.
 */
export function getOverlayFrameState(frames, fps, playbackTime, videoDuration) {
  if (!frames?.length) return { idx: 0, alpha: 0 };
  const rate = Number(fps) > 0 ? Number(fps) : 30;
  const t0 = frames[0].time ?? 0;
  const tN = frames[frames.length - 1].time ?? t0 + (frames.length - 1) / rate;
  const overlaySpan = tN - t0;
  let targetTime = playbackTime;
  if (videoDuration > 0 && overlaySpan > 1e-6) {
    targetTime = t0 + (playbackTime / videoDuration) * overlaySpan;
  } else {
    targetTime = t0 + playbackTime;
  }
  targetTime = Math.max(t0, Math.min(tN, targetTime));

  if (frames.length === 1) return { idx: 0, alpha: 0 };

  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    const tm = overlayFrameTime(frames, mid, t0, rate);
    if (tm <= targetTime) lo = mid;
    else hi = mid;
  }
  const tLo = overlayFrameTime(frames, lo, t0, rate);
  const tHi = overlayFrameTime(frames, hi, t0, rate);
  if (tHi > tLo + 1e-9 && (targetTime - tLo) > (tHi - targetTime)) {
    return { idx: hi, alpha: 0 };
  }
  return { idx: lo, alpha: 0 };
}

export function getOverlayFrameIndex(frames, fps, playbackTime, videoDuration) {
  return getOverlayFrameState(frames, fps, playbackTime, videoDuration).idx;
}

/**
 * Baked/composited clips are often much longer or shorter than the analyzed
 * original. Small iOS duration drift (a few percent) is not a mismatch.
 */
export function overlaySourceLooksMismatched(videoDuration, overlayDuration) {
  const v = Number(videoDuration);
  const o = Number(overlayDuration);
  if (!(v > 1) || !(o > 1)) return false;
  const ratio = v > o ? v / o : o / v;
  return ratio >= 1.45;
}

const OVERLAY_BAKE_FREE_EVENT = "nl-overlay-bake-free";
let overlayBakeBusy = false;

export function tryAcquireOverlayBake() {
  if (overlayBakeBusy) return false;
  overlayBakeBusy = true;
  return true;
}

export function releaseOverlayBake() {
  if (!overlayBakeBusy) return;
  overlayBakeBusy = false;
  try {
    window.dispatchEvent(new Event(OVERLAY_BAKE_FREE_EVENT));
  } catch { /* ignore */ }
}

export function overlayBakeFreeEventName() {
  return OVERLAY_BAKE_FREE_EVENT;
}
