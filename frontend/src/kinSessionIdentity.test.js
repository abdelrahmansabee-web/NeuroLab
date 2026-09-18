import {
  kinAnalysisResultsSig,
  kinAsyncStillCurrent,
  shouldResetKinSessionMedia,
} from "./kinSessionIdentity";

test("first save assigning a record id does not wipe the live overlay", () => {
  expect(shouldResetKinSessionMedia("", "abc123")).toBe(false);
  expect(shouldResetKinSessionMedia(undefined, "abc123")).toBe(false);
  const sig = kinAnalysisResultsSig({
    pre: { csv_filename: "pre.csv", video_filename: "pre.mp4" },
  });
  expect(shouldResetKinSessionMedia("", "abc123", sig, sig)).toBe(false);
});

test("loading a saved record onto a blank form resets media", () => {
  const blank = kinAnalysisResultsSig({});
  const loaded = kinAnalysisResultsSig({
    pre: { csv_filename: "other.csv", video_filename: "other.mp4" },
  });
  expect(shouldResetKinSessionMedia("", "patientB", blank, loaded)).toBe(true);
});

test("loading another patient or leaving a loaded record resets media", () => {
  expect(shouldResetKinSessionMedia("patientA", "patientB")).toBe(true);
  expect(shouldResetKinSessionMedia("patientA", "")).toBe(true);
});

test("same record keeps media", () => {
  expect(shouldResetKinSessionMedia("patientA", "patientA")).toBe(false);
});

test("stale async work is ignored after a switch", () => {
  expect(kinAsyncStillCurrent("patientA", "patientB")).toBe(false);
  expect(kinAsyncStillCurrent("patientA", "patientA")).toBe(true);
});
