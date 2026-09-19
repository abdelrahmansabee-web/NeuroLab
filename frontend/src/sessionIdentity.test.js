import {
  analyzeSourceForOpenSession,
  findPatientForOpenSession,
  kinematicsResultsForOpenSession,
  shouldUseEphemeralSpaceVideo,
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

test("Space /video names are not another patient's restore source", () => {
  expect(shouldUseEphemeralSpaceVideo("IMG_1765.MOV", new Set())).toBe(false);
  expect(shouldUseEphemeralSpaceVideo("IMG_1765.MOV", new Set(["IMG_1764.MOV"]))).toBe(false);
  expect(shouldUseEphemeralSpaceVideo("IMG_1765.MOV", new Set(["IMG_1765.MOV"]))).toBe(true);
  expect(shouldUseEphemeralSpaceVideo("", new Set(["IMG_1765.MOV"]))).toBe(false);
});

test("Analyze can use this patient's recalled original instead of a file-input File", () => {
  const picked = new Blob([new Uint8Array([1, 2, 3])], { type: "video/mp4" });
  picked.name = "live.MOV";
  expect(analyzeSourceForOpenSession({
    file: picked,
    originalBlob: new Blob([new Uint8Array([9])], { type: "video/mp4" }),
    filename: "drive.mp4",
  })).toBe(picked);

  const recalled = analyzeSourceForOpenSession({
    filename: "her_pre.mp4",
    originalBlob: new Blob([new Uint8Array([4, 5, 6])], { type: "video/mp4" }),
  });
  expect(recalled).toBeTruthy();
  expect(recalled.size).toBe(3);
  expect(recalled.name || "").toBe("her_pre.mp4");
  expect(analyzeSourceForOpenSession({ filename: "gone.mp4" })).toBeNull();
});
