import {
  getOverlayFrameState,
  isAppleTouchVideo,
  overlaySourceLooksMismatched,
  releaseOverlayBake,
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

test("overlay pose blends between stored frames for the presented video time", () => {
  const frames = [
    { time: 0, palm: [0.1, 0.1] },
    { time: 0.1, palm: [0.2, 0.2] },
    { time: 0.2, palm: [0.3, 0.3] },
  ];
  expect(getOverlayFrameState(frames, 10, 0, 0.2)).toEqual({ idx: 0, alpha: 0 });
  expect(getOverlayFrameState(frames, 10, 0.04, 0.2)).toEqual({ idx: 0, alpha: 0.4 });
  expect(getOverlayFrameState(frames, 10, 0.09, 0.2)).toEqual({ idx: 0, alpha: 0.9 });
  expect(getOverlayFrameState(frames, 10, 0.2, 0.2)).toEqual({ idx: 1, alpha: 1 });
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
