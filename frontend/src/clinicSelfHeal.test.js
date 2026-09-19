import {
  classifyClinicFault,
  clinicHealBudgetAllows,
  clinicHealNotice,
  noteClinicHealAttempt,
} from "./clinicSelfHeal";

test("upload cut before a job id is a retryable clinic fault", () => {
  const fault = classifyClinicFault({
    context: "analyze-upload",
    name: "AbortError",
    message: "The user aborted a request.",
    hasJobId: false,
  });
  expect(fault.code).toBe("analyze_upload_drop");
  expect(fault.recover).toBe("retry_upload");
  expect(clinicHealNotice(fault, true)).toMatch(/retried the upload/i);
});

test("missing file-input after Drive recall uses the recalled original", () => {
  const fault = classifyClinicFault({
    context: "analyze-upload",
    message: "Please select a file first",
  });
  expect(fault.code).toBe("analyze_missing_file");
  expect(fault.recover).toBe("use_recalled_original");
});

test("overlay 404 after Space rebuild hydrates Drive", () => {
  const fault = classifyClinicFault({
    context: "overlay",
    status: 404,
    message: "Failed to load overlay data (404)",
  });
  expect(fault.code).toBe("overlay_space_csv_gone");
  expect(fault.recover).toBe("hydrate_overlay");
});

test("heal budget stops a retry loop", () => {
  let store = {};
  expect(clinicHealBudgetAllows(store, "analyze_upload_drop", "pre")).toBe(true);
  store = noteClinicHealAttempt(store, "analyze_upload_drop", "pre");
  store = noteClinicHealAttempt(store, "analyze_upload_drop", "pre");
  expect(clinicHealBudgetAllows(store, "analyze_upload_drop", "pre")).toBe(false);
});
