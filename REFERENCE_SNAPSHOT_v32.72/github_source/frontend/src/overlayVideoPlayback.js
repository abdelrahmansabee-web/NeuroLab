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
