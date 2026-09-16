import {
  analysisResultErrorMessage,
  analyzePollExceeded,
  isKinAnalyzeActive,
  setKinAnalyzeActive,
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
