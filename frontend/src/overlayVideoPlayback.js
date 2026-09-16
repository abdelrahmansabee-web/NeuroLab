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

/**
 * Map the presented video time to the overlay sample for that picture.
 * Blend between stored landmark frames (32.72 freeze) so the skeleton follows
 * playback time between samples instead of snapping to the nearer pose.
 *
 * Restored from backup/2026-09-16-full-v32.82: always map the video fraction
 * onto the overlay span. Do not 1:1 lookup on a truncated PRE analysis clock.
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

export function isBrowserNativeOverlayVideoName(name) {
  const lower = String(name || "").toLowerCase();
  return lower.endsWith(".mp4")
    || lower.endsWith(".m4v")
    || lower.endsWith(".mov")
    || lower.endsWith(".webm");
}

/** iOS will not decode a blob URL whose type is empty or octet-stream. */
export function playbackVideoBlob(blob, filename) {
  if (!(blob instanceof Blob) || blob.size <= 0) return blob;
  const type = String(blob.type || "").toLowerCase();
  if (type.startsWith("video/") && type !== "application/octet-stream") return blob;
  const name = String(filename || "").toLowerCase();
  const mime = name.endsWith(".webm")
    ? "video/webm"
    : name.endsWith(".mov")
      ? "video/quicktime"
      : "video/mp4";
  return new Blob([blob], { type: mime });
}

/** Force-replace after Analyze used to revoke the live file then restore stale IDB. */
export function shouldApplyCachedOriginalVideo({ force } = {}) {
  return !force;
}

/**
 * Safari often never fires loadedmetadata on a muted overlay <video> until play().
 * Do not strip sibling src (that 32.83 yield parked POST/HEALTHY and still left PRE empty).
 */
export function kickOverlayVideoElement(video) {
  if (!video) return false;
  try {
    video.load();
  } catch { /* ignore */ }
  if (!isAppleTouchVideo() || typeof video.play !== "function") return true;
  try {
    video.muted = true;
    const playing = video.play();
    if (playing && typeof playing.then === "function") {
      playing.then(() => {
        try {
          video.pause();
        } catch { /* ignore */ }
      }).catch(() => {});
    }
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
