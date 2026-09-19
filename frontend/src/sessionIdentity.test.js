import {
  findPatientForOpenSession,
  kinAnalysisResultsSig,
  kinAsyncStillCurrent,
  kinematicsResultsForOpenSession,
  shouldResetKinSessionMedia,
} from "./sessionIdentity";

test("open session kinematics ignore leftover global KIN_LS", () => {
  const his = { pre: { video_filename: "man_pre.mp4" }, post: { video_filename: "man_post.mp4" } };
  expect(kinematicsResultsForOpenSession({}, his)).toEqual({});
  expect(kinematicsResultsForOpenSession(null, his)).toEqual({});
  expect(kinematicsResultsForOpenSession({ pre: { video_filename: "her_pre.mp4" } }, his)).toEqual({
    pre: { video_filename: "her_pre.mp4" },
  });
});

test("findPatientForOpenSession does not match Study ID against another patient's _id", () => {
  const man = {
    _id: "115",
    demographics: { participantId: "101", name: "Ahmed" },
    kinematics: { analysisResults: { pre: { video_filename: "man.mp4" } } },
  };
  const woman = {
    _id: "u-woman",
    demographics: { participantId: "120", name: "Fatma" },
    kinematics: { analysisResults: { pre: { video_filename: "her.mp4" } } },
  };
  expect(findPatientForOpenSession([man, woman], {
    _loadedId: "u-woman",
    demographics: { participantId: "120" },
  })).toBe(woman);
  expect(findPatientForOpenSession([man, woman], {
    demographics: { participantId: "120" },
  })).toBe(woman);
  expect(findPatientForOpenSession([man, woman], {
    demographics: { participantId: "115" },
  })).toBe(null);
  expect(findPatientForOpenSession([man, woman], { _loadedId: "115" })).toBe(man);
});

test("findPatientForOpenSession refuses a Study ID that hits two rows", () => {
  const a = { _id: "a", demographics: { participantId: "115" } };
  const b = { _id: "b", demographics: { participantId: "115" } };
  expect(findPatientForOpenSession([a, b], { demographics: { participantId: "115" } })).toBe(null);
});

test("first save assigning a folder key does not wipe the live overlay", () => {
  const sig = kinAnalysisResultsSig({
    pre: { csv_filename: "pre.csv", video_filename: "pre.mp4" },
  });
  expect(shouldResetKinSessionMedia("", "101_Fatma", sig, sig)).toBe(false);
  expect(shouldResetKinSessionMedia("", "101_Fatma")).toBe(false);
});

test("loading another patient or leaving a loaded record resets media", () => {
  expect(shouldResetKinSessionMedia("101_Ahmed", "120_Fatma")).toBe(true);
  expect(shouldResetKinSessionMedia("101_Ahmed", "")).toBe(true);
  const blank = kinAnalysisResultsSig({});
  const loaded = kinAnalysisResultsSig({
    pre: { csv_filename: "other.csv", video_filename: "other.mp4" },
  });
  expect(shouldResetKinSessionMedia("", "120_Fatma", blank, loaded)).toBe(true);
});

test("stale async work is ignored after a switch", () => {
  expect(kinAsyncStillCurrent("101_Ahmed", "120_Fatma")).toBe(false);
  expect(kinAsyncStillCurrent("120_Fatma", "120_Fatma")).toBe(true);
});
