import {
  analysisResultErrorMessage,
  analyzeJobIdForPhase,
  analyzePollExceeded,
  clearAnalyzeUi,
  isAnalyzeLeaveAbort,
  isKinAnalyzeActive,
  isTransientAnalyzePollError,
  readAnalyzeUi,
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
