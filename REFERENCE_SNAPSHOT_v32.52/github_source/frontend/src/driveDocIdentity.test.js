import {
  canonicalDriveName,
  clinicReportDriveName,
  documentKind,
  driveNameCandidates,
} from "./driveDocIdentity";

describe("driveDocIdentity", () => {
  test("collapses dated PDF exports onto one patient file", () => {
    expect(documentKind("report_115_Ahmet_2026-09-14.pdf")).toBe("clinic_report");
    expect(canonicalDriveName("report_115_Ahmet_2026-09-14.pdf", "115_Ahmet_sever")).toBe(
      "115_Ahmet_sever.pdf",
    );
    expect(clinicReportDriveName("115_Ahmet_sever")).toBe("115_Ahmet_sever.pdf");
  });

  test("keeps baked validation and original analysis as separate slots", () => {
    expect(canonicalDriveName("pre_validation_unified.webm")).toBe("pre_validation.mp4");
    expect(canonicalDriveName("pre_original.mp4")).toBe("pre_validation_original.mp4");
    expect(canonicalDriveName("baseline_validation.mp4")).toBe("healthy_validation.mp4");
  });

  test("restore candidates include old alias names", () => {
    const names = driveNameCandidates("pre_validation.mp4");
    expect(names).toEqual(
      expect.arrayContaining(["pre_validation.mp4", "pre_validation_unified.mp4", "pre_validation.webm"]),
    );
  });
});
