import {
  OVERLAY_VIDEO_PRELOAD,
  enqueueOverlayVideoAttach,
  getOverlayFrameState,
  isAppleTouchVideo,
  overlayLivePaintFromCurrentTime,
  overlayPlaybackPaintStalled,
  overlayPlayerMountDelayMs,
  overlaySourceLooksMismatched,
  overlayVideoLooksStalled,
  overlayVideoShouldRetryError,
  releaseOverlayBake,
  reloadOverlayVideoElement,
  resetOverlayVideoAttachQueueForTests,
  shouldRestartPlayback,
  tryAcquireOverlayBake,
} from "./overlayVideoPlayback";

test("replay starts over when the clip has ended", () => {
  expect(shouldRestartPlayback({ ended: true, currentTime: 12, duration: 12 })).toBe(true);
  expect(shouldRestartPlayback({ ended: false, currentTime: 11.95, duration: 12 })).toBe(true);
  expect(shouldRestartPlayback({ ended: false, currentTime: 3.2, duration: 12 })).toBe(false);
  expect(shouldRestartPlayback({ ended: false, currentTime: 0, duration: 0 })).toBe(false);
});

test("Apple touch detection is false in jsdom by default", () => {
  expect(isAppleTouchVideo()).toBe(false);
});

test("live playback with RVFC does not paint from lagging currentTime", () => {
  expect(overlayLivePaintFromCurrentTime({
    playing: true,
    useVideoFrameCallback: true,
    rafFallback: false,
  })).toBe(false);
  expect(overlayLivePaintFromCurrentTime({
    playing: true,
    useVideoFrameCallback: true,
    rafFallback: true,
  })).toBe(true);
  expect(overlayLivePaintFromCurrentTime({
    playing: false,
    useVideoFrameCallback: true,
    rafFallback: false,
  })).toBe(true);
  expect(overlayLivePaintFromCurrentTime({
    playing: true,
    useVideoFrameCallback: false,
    rafFallback: false,
  })).toBe(true);
});

test("iOS currentTime behind mediaTime is not a stalled overlay paint", () => {
  expect(overlayPlaybackPaintStalled({
    currentTime: 0.85,
    lastPaintMediaTime: 1.0,
    paused: false,
    ended: false,
  })).toBe(false);
  expect(overlayPlaybackPaintStalled({
    currentTime: 1.2,
    lastPaintMediaTime: 1.0,
    paused: false,
    ended: false,
  })).toBe(true);
  expect(overlayPlaybackPaintStalled({
    currentTime: 1.2,
    lastPaintMediaTime: 1.0,
    paused: true,
    ended: false,
  })).toBe(false);
});

test("overlay pose blends between stored frames for the presented video time", () => {
  const frames = [
    { time: 0, palm: [0.1, 0.1] },
    { time: 0.1, palm: [0.2, 0.2] },
    { time: 0.2, palm: [0.3, 0.3] },
  ];
  expect(getOverlayFrameState(frames, 10, 0, 0.2)).toEqual({ idx: 0, alpha: 0 });
  const mid = getOverlayFrameState(frames, 10, 0.04, 0.2);
  expect(mid.idx).toBe(0);
  expect(mid.alpha).toBeCloseTo(0.4, 10);
  const near = getOverlayFrameState(frames, 10, 0.09, 0.2);
  expect(near.idx).toBe(0);
  expect(near.alpha).toBeCloseTo(0.9, 10);
  expect(getOverlayFrameState(frames, 10, 0.2, 0.2)).toEqual({ idx: 1, alpha: 1 });
});

test("32.82 backup clock maps video fraction onto overlay span so long PRE cannot finish first", () => {
  const videoDuration = 9 * 60 + 18;
  const playbackTime = 8 * 60 + 4;
  const frames = [];
  for (let i = 0; i <= 5357; i += 1) frames.push({ time: i / 10 });
  const st = getOverlayFrameState(frames, 10, playbackTime, videoDuration);
  expect(st.idx / 5357).toBeCloseTo(playbackTime / videoDuration, 2);
  const short = [];
  for (let i = 0; i <= 288; i += 1) short.push({ time: i / 10 });
  expect(getOverlayFrameState(short, 10, 15, 30).idx).toBe(144);
});

test("duration mismatch ignores small iOS drift and flags a baked-clip swap", () => {
  expect(overlaySourceLooksMismatched(12.08, 12)).toBe(false);
  expect(overlaySourceLooksMismatched(24, 12)).toBe(true);
  expect(overlaySourceLooksMismatched(0, 12)).toBe(false);
});

test("overlay bake lock allows only one MediaRecorder at a time", () => {
  releaseOverlayBake();
  expect(tryAcquireOverlayBake()).toBe(true);
  expect(tryAcquireOverlayBake()).toBe(false);
  releaseOverlayBake();
  expect(tryAcquireOverlayBake()).toBe(true);
  releaseOverlayBake();
});

test("third overlay player waits before mounting next to live clips", () => {
  expect(overlayPlayerMountDelayMs(0)).toBe(0);
  expect(overlayPlayerMountDelayMs(1)).toBeGreaterThan(0);
  expect(overlayPlayerMountDelayMs(2)).toBe(overlayPlayerMountDelayMs(1));
});

test("overlay video stall is the empty 0:00/0:00 third-player case", () => {
  expect(overlayVideoLooksStalled({
    readyState: 0,
    duration: 0,
    videoWidth: 0,
    elapsedMs: 200,
  })).toBe(false);
  expect(overlayVideoLooksStalled({
    readyState: 0,
    duration: NaN,
    videoWidth: 0,
    elapsedMs: 1600,
  })).toBe(true);
  expect(overlayVideoLooksStalled({
    readyState: 1,
    duration: 8.1,
    videoWidth: 0,
    elapsedMs: 1600,
  })).toBe(false);
});

test("iOS media error 4 retries until the reload budget is spent", () => {
  expect(overlayVideoShouldRetryError(4, 0)).toBe(true);
  expect(overlayVideoShouldRetryError(3, 1)).toBe(true);
  expect(overlayVideoShouldRetryError(4, 2)).toBe(false);
  expect(overlayVideoShouldRetryError(1, 0)).toBe(false);
});

test("reload restores src with metadata preload", () => {
  const calls = [];
  const video = {
    src: "blob:phase-pre",
    getAttribute: (name) => (name === "src" ? "blob:phase-pre" : null),
    setAttribute: (name, value) => {
      if (name === "src") video.src = value;
    },
    removeAttribute: (name) => {
      if (name === "src") video.src = "";
    },
    pause: () => calls.push("pause"),
    load: () => calls.push("load"),
  };
  expect(reloadOverlayVideoElement(video)).toBe(true);
  expect(video.src).toBe("blob:phase-pre");
  expect(video.preload).toBe(OVERLAY_VIDEO_PRELOAD);
  expect(calls).toEqual(["pause", "load", "load"]);
});

test("overlay video attach queue runs tasks in order", async () => {
  resetOverlayVideoAttachQueueForTests();
  const order = [];
  await Promise.all([
    enqueueOverlayVideoAttach(() => { order.push("a"); }),
    enqueueOverlayVideoAttach(() => { order.push("b"); }),
    enqueueOverlayVideoAttach(() => { order.push("c"); }),
  ]);
  expect(order).toEqual(["a", "b", "c"]);
  resetOverlayVideoAttachQueueForTests();
});
