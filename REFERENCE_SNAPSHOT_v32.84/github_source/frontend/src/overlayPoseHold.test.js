import { holdTrackingNoise, overlayTrackingNoisePx, resetHoldIfSeek } from "./overlayPoseHold";

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
