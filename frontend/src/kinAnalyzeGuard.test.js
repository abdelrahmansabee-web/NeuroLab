import {
  analysisResultErrorMessage,
  analyzeJobIdForPhase,
  analyzePollExceeded,
  clearAnalyzeUi,
  isAnalyzeLeaveAbort,
  isClinicFileLocked,
  isKinAnalyzeActive,
  isRecallingBlocked,
  setClinicFileLock,
  isTransientAnalyzePollError,
  readAnalyzeUi,
  isStaleAnalyzing,
  resetStaleAnalyzeStatuses,
  setKinAnalyzeActive,
  shouldResumeAnalyze,
  writeAnalyzeUi,
} from "./kinAnalyzeGuard";

test("analyze-active flag turns off after an explicit clear", () => {
  setKinAnalyzeActive(true);
  expect(isKinAnalyzeActive()).toBe(true);
  setKinAnalyzeActive(false);
  expect(isKinAnalyzeActive()).toBe(false);
});

test("Recalling law blocks Drive recall while a local file is staged or Analyze runs", () => {
  setKinAnalyzeActive(false);
  setClinicFileLock(false);
  expect(isRecallingBlocked()).toBe(false);
  setClinicFileLock(true);
  expect(isClinicFileLocked()).toBe(true);
  expect(isRecallingBlocked()).toBe(true);
  setClinicFileLock(false);
  setKinAnalyzeActive(true);
  expect(isRecallingBlocked()).toBe(true);
  setKinAnalyzeActive(false);
  expect(isRecallingBlocked()).toBe(false);
});

test("server error payload is a thrown-message string, not a silent skip", () => {
  expect(analysisResultErrorMessage({ error: "pose failed" })).toBe("pose failed");
  expect(analysisResultErrorMessage({ ok: true })).toBe("");
  expect(analysisResultErrorMessage(null)).toBe("");
});

test("analyze poll stops after the clinic max attempts", () => {
  expect(analyzePollExceeded(859)).toBe(false);
  expect(analyzePollExceeded(860)).toBe(true);
});

test("analyze UI keeps the server job id across section changes", () => {
  clearAnalyzeUi();
  writeAnalyzeUi({ phase: "pre", jobId: "job-her", pct: 22, step: "Extracting pose…" });
  const ui = readAnalyzeUi();
  expect(ui.jobId).toBe("job-her");
  expect(analyzeJobIdForPhase("pre", ui, {})).toBe("job-her");
  expect(analyzeJobIdForPhase("pre", { phase: "post" }, { pre: { jobId: "from-fd" } })).toBe("from-fd");
  expect(shouldResumeAnalyze("analyzing", "job-her")).toBe(true);
  expect(shouldResumeAnalyze("uploaded", "job-her")).toBe(false);
  expect(shouldResumeAnalyze("analyzing", "")).toBe(false);
  expect(isStaleAnalyzing("analyzing", "")).toBe(true);
  expect(isStaleAnalyzing("analyzing", "job-her")).toBe(false);
  expect(isStaleAnalyzing("analyzing", "", true)).toBe(false);
  expect(isStaleAnalyzing("uploaded", "")).toBe(false);
  const stuck = resetStaleAnalyzeStatuses(
    { status_pre: "analyzing", status_post: "analyzing", analyzeJobs: { post: { jobId: "job-live" } } },
    ["pre", "post"],
    null,
    (phase) => phase === "baseline",
  );
  expect(stuck.status_pre).toBe("uploaded");
  expect(stuck.status_post).toBe("analyzing");
  expect(stuck.analyzeJobs.post.jobId).toBe("job-live");
  expect(resetStaleAnalyzeStatuses(
    { status_pre: "analyzing" },
    ["pre"],
    null,
    (phase) => phase === "pre",
  )).toBe(null);
  clearAnalyzeUi();
});

test("background fetch drops are retried; leaving a section is not a cancel", () => {
  const live = { aborted: false };
  expect(isTransientAnalyzePollError(new TypeError("Failed to fetch"), live)).toBe(true);
  expect(isTransientAnalyzePollError(new Error("Progress poll failed (502)"), live)).toBe(true);
  expect(isTransientAnalyzePollError(Object.assign(new Error("aborted"), { name: "AbortError" }), { aborted: true })).toBe(false);
  expect(isAnalyzeLeaveAbort(Object.assign(new Error("aborted"), { name: "AbortError" }), true)).toBe(true);
  expect(isAnalyzeLeaveAbort(Object.assign(new Error("aborted"), { name: "AbortError" }), false)).toBe(false);
});
