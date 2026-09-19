import {
  holdBodyDisplay,
  holdDisplayLandmark,
  holdFingerCanvas,
  holdTrackingNoise,
  overlayBodyRestPx,
  overlayTrackingNoisePx,
  resetHoldIfSeek,
} from "./overlayPoseHold";

test("rest jitter under 2px is held; real motion updates", () => {
  const store = {};
  const a = holdTrackingNoise(store, "palm", [100, 100], 2);
  const b = holdTrackingNoise(store, "palm", [100.8, 100.4], 2);
  const c = holdTrackingNoise(store, "palm", [108, 101], 2);
  expect(b).toBe(a);
  expect(c[0]).toBe(108);
  expect(c[1]).toBe(101);
});

test("missing point stays missing", () => {
  expect(holdTrackingNoise({}, "palm", null)).toBeNull();
});

test("seek clears the hold store", () => {
  const store = { palm: [1, 1], _idx: 10 };
  resetHoldIfSeek(store, 40);
  expect(store.palm).toBeUndefined();
  expect(store._idx).toBe(40);
});

test("noise floor is at least 2px", () => {
  expect(overlayTrackingNoisePx(1280, 720)).toBeGreaterThanOrEqual(2);
});

test("body rest floor swallows detector wander", () => {
  expect(overlayBodyRestPx(1280, 720)).toBeGreaterThanOrEqual(8);
});

test("display hold ignores camera/MediaPipe jitter and follows real body motion", () => {
  const store = {};
  const still = holdDisplayLandmark(store, "shoulder", [0.40, 0.30], 1000, 800, 10);
  const noise = holdDisplayLandmark(store, "shoulder", [0.401, 0.301], 1000, 800, 11);
  const move = holdDisplayLandmark(store, "shoulder", [0.45, 0.30], 1000, 800, 12);
  expect(noise).toBe(still);
  expect(move[0]).toBeCloseTo(450, 8);
  expect(move[1]).toBeCloseTo(240, 8);
});

test("independent joint noise does not move a still body", () => {
  const store = {};
  const rest = {
    shoulder: [0.40, 0.30],
    elbow: [0.42, 0.48],
    wrist: [0.44, 0.62],
    trunk: [0.38, 0.34],
    lshoulder: [0.32, 0.30],
    rshoulder: [0.40, 0.30],
    lhip: [0.34, 0.58],
    rhip: [0.40, 0.58],
  };
  const a = holdBodyDisplay(store, rest, 1000, 800, 10);
  const jitter = {
    ...rest,
    shoulder: [0.411, 0.309],
    elbow: [0.414, 0.469],
    wrist: [0.449, 0.631],
    trunk: [0.371, 0.348],
  };
  const b = holdBodyDisplay(store, jitter, 1000, 800, 11);
  expect(b.shoulder).toEqual(a.shoulder);
  expect(b.elbow).toEqual(a.elbow);
  expect(b.wrist).toEqual(a.wrist);
  expect(b.trunk).toEqual(a.trunk);
});

test("a real reach updates the arm and keeps the still torso", () => {
  const store = {};
  const rest = {
    shoulder: [0.40, 0.30],
    elbow: [0.42, 0.48],
    wrist: [0.44, 0.62],
    trunk: [0.38, 0.34],
    lshoulder: [0.32, 0.30],
    rshoulder: [0.40, 0.30],
  };
  const a = holdBodyDisplay(store, rest, 1000, 800, 10);
  const reach = {
    ...rest,
    elbow: [0.50, 0.40],
    wrist: [0.62, 0.28],
  };
  const b = holdBodyDisplay(store, reach, 1000, 800, 11);
  expect(b.shoulder).toEqual(a.shoulder);
  expect(b.trunk).toEqual(a.trunk);
  expect(b.wrist[0]).toBeCloseTo(620, 8);
  expect(b.wrist[1]).toBeCloseTo(224, 8);
});

test("a shared camera shift moves the whole figure together", () => {
  const store = {};
  const rest = {
    shoulder: [0.40, 0.30],
    elbow: [0.42, 0.48],
    trunk: [0.38, 0.34],
    lshoulder: [0.32, 0.30],
    rshoulder: [0.40, 0.30],
    lhip: [0.34, 0.58],
    rhip: [0.40, 0.58],
  };
  const a = holdBodyDisplay(store, rest, 1000, 800, 10);
  const shifted = {};
  Object.keys(rest).forEach((k) => {
    shifted[k] = [rest[k][0] + 0.03, rest[k][1]];
  });
  const b = holdBodyDisplay(store, shifted, 1000, 800, 11);
  expect(b.shoulder[0] - a.shoulder[0]).toBeCloseTo(30, 8);
  expect(b.elbow[0] - a.elbow[0]).toBeCloseTo(30, 8);
  expect(b.trunk[0] - a.trunk[0]).toBeCloseTo(30, 8);
  expect(b.shoulder[1]).toEqual(a.shoulder[1]);
});

test("finger rest shimmer is held to the wrist; a real finger move updates", () => {
  const store = {};
  const wrist = [400, 500];
  const tip = [430, 470];
  const a = holdFingerCanvas(store, "index:tip", tip, wrist, 1000, 800, 10);
  const noise = holdFingerCanvas(store, "index:tip", [434, 473], [401, 501], 1000, 800, 11);
  expect(noise[0] - 401).toBeCloseTo(a[0] - 400, 8);
  expect(noise[1] - 501).toBeCloseTo(a[1] - 500, 8);
  const move = holdFingerCanvas(store, "index:tip", [490, 420], [400, 500], 1000, 800, 12);
  expect(move[0]).toBeCloseTo(490, 8);
  expect(move[1]).toBeCloseTo(420, 8);
});
