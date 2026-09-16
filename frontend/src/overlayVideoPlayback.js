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

export const OVERLAY_PAINT_STALL_SEC = 0.12;

/**
 * Live iPad paints must use RVFC mediaTime. video.currentTime lags the picture on iOS.
 * RAF fallback (no RVFC, or RVFC threw) still paints from currentTime.
 */
export function overlayLivePaintFromCurrentTime({
  playing,
  useVideoFrameCallback,
  rafFallback,
} = {}) {
  if (!playing) return true;
  if (useVideoFrameCallback && !rafFallback) return false;
  return true;
}

/**
 * Playback moved forward without a paint. currentTime behind last mediaTime is
 * iOS clock lag, not a stalled callback — do not use Math.abs.
 */
export function overlayPlaybackPaintStalled({
  currentTime,
  lastPaintMediaTime,
  paused,
  ended,
  threshold = OVERLAY_PAINT_STALL_SEC,
} = {}) {
  if (paused || ended) return false;
  const t = Number(currentTime);
  const last = Number(lastPaintMediaTime);
  if (!Number.isFinite(t) || !Number.isFinite(last)) return false;
  return (t - last) > threshold;
}

function overlayFrameTime(frames, idx, t0, fps) {
  const frame = frames[idx];
  if (!frame) return t0 + idx / fps;
  return frame.time ?? t0 + idx / fps;
}

/** Ignore sub-frame Safari vs CSV length noise; still catch 60fps ms truncation. */
export const OVERLAY_SHORT_SPAN_PAD_SEC = 0.05;

/**
 * Pose CSV time was stamped with int(1000/fps) milliseconds. That clock runs
 * slow, so on a long PRE clip (rest + reach) overlay duration is shorter than
 * Safari's media time and 1:1 lookup finishes the skeleton first. POST and
 * healthy clips are short enough that the same error is not visible.
 *
 * Scale playback into the overlay span only when the overlay is shorter.
 * Never scale onto a shorter HTMLMediaElement.duration — that iOS drift is
 * what made the skeleton run ahead in 32.87.
 */
export function overlayPlaybackTargetTime({
  playbackTime,
  videoDuration,
  t0,
  tN,
} = {}) {
  const tStart = Number(t0);
  const tEnd = Number(tN);
  const tPlay = Number(playbackTime);
  const start = Number.isFinite(tStart) ? tStart : 0;
  if (!Number.isFinite(tPlay)) return start;
  const span = Number.isFinite(tEnd) ? tEnd - start : NaN;
  const dur = Number(videoDuration);
  if (Number.isFinite(dur) && Number.isFinite(span) && dur > span + OVERLAY_SHORT_SPAN_PAD_SEC && span > 1e-6) {
    return start + (Math.max(0, tPlay) / dur) * span;
  }
  return tPlay;
}

/**
 * Map the presented video time to the overlay sample for that picture.
 * Blend between stored landmark frames (32.72 freeze) so the skeleton follows
 * playback time between samples instead of snapping to the nearer pose.
 *
 * frame.time is the analyzed video clock. Do not shrink it onto a short
 * HTMLMediaElement.duration (iOS). Do stretch playback across a short overlay
 * span — truncated PRE analysis clocks finish the reach before the person.
 */
export function getOverlayFrameState(frames, fps, playbackTime, videoDuration) {
  if (!frames?.length) return { idx: 0, alpha: 0 };
  const rate = Number(fps) > 0 ? Number(fps) : 30;
  const t0 = frames[0].time ?? 0;
  const tN = frames[frames.length - 1].time ?? t0 + (frames.length - 1) / rate;
  let targetTime = overlayPlaybackTargetTime({
    playbackTime,
    videoDuration,
    t0,
    tN,
  });
  if (!Number.isFinite(targetTime)) targetTime = t0;
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
  const alpha = tHi > tLo + 1e-9
    ? Math.max(0, Math.min(1, (targetTime - tLo) / (tHi - tLo)))
    : 0;
  return { idx: lo, alpha };
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

/** Compact 3-up iPad: never fully buffer every clip at once. */
export const OVERLAY_VIDEO_PRELOAD = "metadata";
export const OVERLAY_VIDEO_STALL_MS = 1400;
export const OVERLAY_VIDEO_RELOAD_MAX = 2;
export const OVERLAY_PLAYER_STAGGER_MS = 560;

/** Mount the next overlay player only after earlier ones have a head start. */
export function overlayPlayerMountDelayMs(alreadyMountedCount) {
  const n = Math.max(0, Number(alreadyMountedCount) || 0);
  return n <= 0 ? 0 : OVERLAY_PLAYER_STAGGER_MS;
}

/** iOS often never fires error or loadedmetadata on the 3rd concurrent <video>. */
export function overlayVideoLooksStalled({
  readyState,
  duration,
  videoWidth,
  elapsedMs,
  stallMs = OVERLAY_VIDEO_STALL_MS,
} = {}) {
  const elapsed = Number(elapsedMs);
  if (!Number.isFinite(elapsed) || elapsed < stallMs) return false;
  const rs = Number(readyState) || 0;
  const dur = Number(duration);
  const w = Number(videoWidth) || 0;
  if (rs >= 1 && Number.isFinite(dur) && dur > 0.05) return false;
  if (rs >= 2 && w > 1) return false;
  return true;
}

export function overlayVideoShouldRetryError(mediaErrorCode, reloadAttempts) {
  if ((Number(reloadAttempts) || 0) >= OVERLAY_VIDEO_RELOAD_MAX) return false;
  const code = Number(mediaErrorCode);
  return code === 2 || code === 3 || code === 4;
}

export function reloadOverlayVideoElement(video) {
  if (!video) return false;
  const src = video.getAttribute("src") || video.src || "";
  if (!src) return false;
  try {
    video.pause();
  } catch { /* ignore */ }
  try {
    video.removeAttribute("src");
    video.load();
  } catch { /* ignore */ }
  video.setAttribute("src", src);
  video.preload = OVERLAY_VIDEO_PRELOAD;
  try {
    video.load();
  } catch { /* ignore */ }
  return true;
}

let overlayAttachTail = Promise.resolve();

/** One overlay clip calls load() at a time so iPad decode does not drop the third. */
export function enqueueOverlayVideoAttach(task) {
  const run = typeof task === "function" ? task : () => {};
  const next = overlayAttachTail.then(() => run());
  overlayAttachTail = next.then(() => undefined, () => undefined);
  return next;
}

export function resetOverlayVideoAttachQueueForTests() {
  overlayAttachTail = Promise.resolve();
}

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
