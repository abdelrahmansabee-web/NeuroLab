import { KIN_RESULTS_LS_KEY, loadLiveKinResults } from "./kinMetrics";

test("loadLiveKinResults does not read another patient's global KIN_LS", () => {
  localStorage.setItem(KIN_RESULTS_LS_KEY, JSON.stringify({
    pre: { video_filename: "man.mp4" },
  }));
  expect(loadLiveKinResults({
    kinematics: { analysisResults: { pre: { video_filename: "her.mp4" } } },
  }).pre.video_filename).toBe("her.mp4");
  expect(loadLiveKinResults({ kinematics: {} })).toEqual({});
  localStorage.removeItem(KIN_RESULTS_LS_KEY);
});
