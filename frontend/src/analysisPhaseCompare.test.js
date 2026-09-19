import {
  analysisProfileForRole,
  clinicTrialRoleFromPhase,
  compareClinicPhasePipelines,
  diffPhaseOverlayClocks,
  inferTrialRoleFromFilename,
  resolveAnalysisArm,
  summarizeOverlayClock,
  videoAnalyzeFormFields,
} from "./analysisPhaseCompare";

test("pre and post send the same analysis request except the slot name", () => {
  const cmp = compareClinicPhasePipelines({ strokeSide: "left" });
  expect(cmp.prePostSameRequest).toBe(true);
  expect(cmp.pre.phase).toBe("pre");
  expect(cmp.post.phase).toBe("post");
  expect(cmp.pre.trial_role).toBe("pre");
  expect(cmp.post.trial_role).toBe("post");
  expect(cmp.preArm).toBe("left");
  expect(cmp.postArm).toBe("left");
  expect(cmp.preProfile).toBe("affected");
  expect(cmp.postProfile).toBe("affected");
  expect(cmp.overlayBuilderShared).toBe(true);
});

test("healthy side uses the contralateral arm and the reference window profile", () => {
  expect(resolveAnalysisArm("baseline", "left", "left")).toBe("right");
  expect(resolveAnalysisArm("healthy", "right", "right")).toBe("left");
  expect(clinicTrialRoleFromPhase("baseline")).toBe("healthy");
  expect(analysisProfileForRole("healthy")).toBe("reference");
  const cmp = compareClinicPhasePipelines({ strokeSide: "right" });
  expect(cmp.baselineArm).toBe("left");
  expect(cmp.baselineProfile).toBe("reference");
  expect(cmp.preArm).toBe(cmp.postArm);
  expect(cmp.baselineArm).not.toBe(cmp.preArm);
});

test("client still labels every video arm_type paretic; arm math is the phase slot", () => {
  expect(videoAnalyzeFormFields("baseline", { strokeSide: "right" }).arm_type).toBe("paretic");
  expect(videoAnalyzeFormFields("pre", { strokeSide: "right" }).arm_type).toBe("paretic");
  expect(resolveAnalysisArm("baseline", "right", "right")).toBe("left");
});

test("filename substring inference can disagree with the clinic slot", () => {
  expect(inferTrialRoleFromFilename("pre_20260916_120000_posture_reach.csv")).toBe("post");
  expect(inferTrialRoleFromFilename("pre_20260916_120000_control_arm.csv")).toBe("healthy");
  expect(inferTrialRoleFromFilename("post_20260916_120000_IMG_1234.csv")).toBe("post");
  expect(inferTrialRoleFromFilename("baseline_20260916_120000_healthy_validation_original.csv")).toBe("healthy");
  expect(clinicTrialRoleFromPhase("pre")).toBe("pre");
});

test("overlay clock summary is phase-agnostic", () => {
  const overlay = {
    overlay_version: 44,
    affected_side: "left",
    fps: 60,
    duration_sec: 8.2,
    frames: [{ time: 0 }, { time: 8.2 }],
  };
  expect(summarizeOverlayClock(overlay)).toEqual({
    overlay_version: 44,
    affected_side: "left",
    fps: 60,
    duration_sec: 8.2,
    nframes: 2,
    t0: 0,
    tN: 8.2,
  });
});

test("PRE vs POST overlay clocks flag arm or fps outliers only", () => {
  const shared = {
    overlay_version: 44,
    fps: 60,
    duration_sec: 10,
    frames: [{ time: 0 }, { time: 10 }],
  };
  const same = diffPhaseOverlayClocks({
    pre: { ...shared, affected_side: "right" },
    post: { ...shared, affected_side: "right" },
    baseline: { ...shared, affected_side: "left" },
  });
  expect(same.diffs).toEqual([]);

  const mismatched = diffPhaseOverlayClocks({
    pre: { ...shared, affected_side: "left", fps: 30 },
    post: { ...shared, affected_side: "right", fps: 60 },
    baseline: { ...shared, affected_side: "left" },
  });
  expect(mismatched.diffs).toEqual(expect.arrayContaining([
    "pre_post_affected_side",
    "pre_post_fps",
    "pre_baseline_same_arm",
  ]));
});
