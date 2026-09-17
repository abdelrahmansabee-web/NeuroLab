import {
  driveKindsFromNames,
  evaluateRecallPieces,
  formatRecallToast,
  planPatientRecall,
  recallPoolSize,
  shouldReuseRecentRecall,
  shouldWaitForPatientsBeforeRecall,
  summarizeRecallRows,
} from "./driveSessionRestore";

function patient({ id, name, pre, post, baseline } = {}) {
  return {
    _id: id || "x",
    demographics: { participantId: id || "101", name: name || "Ada" },
    kinematics: {
      analysisResults: {
        ...(pre ? { pre } : {}),
        ...(post ? { post } : {}),
        ...(baseline ? { baseline } : {}),
      },
    },
  };
}

describe("driveSessionRestore", () => {
  test("plans analyzed phases from JSON and Drive filenames", () => {
    const plan = planPatientRecall(
      patient({
        id: "115",
        name: "Ada",
        pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1.2 },
      }),
      ["pre_validation_original.mp4", "pre_validation_overlay.json", "115_Ada.pdf"],
    );
    expect(plan.patientKey).toBe("115_Ada");
    expect(plan.wantPdf).toBe(true);
    expect(plan.phases[0].expected).toBe(true);
    expect(plan.phases[1].expected).toBe(false);
    expect(driveKindsFromNames(["pre_validation_unified.webm"]).has("pre_validation")).toBe(true);
  });

  test("names missing original video, overlay, and PDF after a Drive miss", () => {
    const plan = planPatientRecall(
      patient({
        id: "115",
        pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1.1 },
      }),
      [],
    );
    const row = evaluateRecallPieces(plan, {
      cacheByPhase: {
        pre: { kinematicsSnapshot: { movement_time_sec: 1.1, csv_filename: "a.csv" } },
      },
      pdfOk: false,
      kinByPhase: { pre: { movement_time_sec: 1.1 } },
    });
    expect(row.complete).toBe(false);
    expect(row.missing).toEqual(
      expect.arrayContaining(["Pre original video", "Pre overlay"]),
    );
    expect(row.missing).not.toContain("Clinic PDF");
    expect(row.missing).not.toContain("Pre analysis");
  });

  test("counts a fully recalled session when bytes and PDF are present", () => {
    const overlay = { frames: [{ t: 0 }] };
    const original = new Blob([new Uint8Array([1, 2, 3])], { type: "video/mp4" });
    const plan = planPatientRecall(
      patient({
        id: "101",
        pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1 },
      }),
      ["pre_validation_original.mp4", "pre_validation_overlay.json", "101_Ada.pdf"],
    );
    const row = evaluateRecallPieces(plan, {
      cacheByPhase: {
        pre: {
          overlay,
          originalVideoBlob: original,
          kinematicsSnapshot: { csv_filename: "a.csv", movement_time_sec: 1 },
        },
      },
      pdfOk: true,
    });
    expect(row.complete).toBe(true);
    expect(row.missing).toEqual([]);
    const summary = summarizeRecallRows([row]);
    expect(summary.complete).toBe(1);
    expect(formatRecallToast(summary)).toMatch(/Recalled 1 session/);
  });

  test("does not require baked validation unless Drive or JSON has it", () => {
    const overlay = { frames: [{ t: 0 }] };
    const original = new Blob([new Uint8Array([9])], { type: "video/mp4" });
    const plan = planPatientRecall(
      patient({
        id: "108",
        pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1 },
      }),
      ["pre_validation_original.mp4", "pre_validation_overlay.json"],
    );
    expect(plan.phases[0].wantUnified).toBe(false);
    expect(plan.wantPdf).toBe(false);
    const row = evaluateRecallPieces(plan, {
      cacheByPhase: {
        pre: { overlay, originalVideoBlob: original, kinematicsSnapshot: { csv_filename: "a.csv" } },
      },
      pdfOk: false,
    });
    expect(row.complete).toBe(true);
    expect(row.missing).not.toContain("Clinic PDF");
  });

  test("requires clinic PDF only when Drive listing has one", () => {
    const overlay = { frames: [{ t: 0 }] };
    const original = new Blob([new Uint8Array([9])], { type: "video/mp4" });
    const plan = planPatientRecall(
      patient({
        id: "108",
        name: "Ada",
        pre: { csv_filename: "a.csv", video_filename: "a.mp4", movement_time_sec: 1 },
      }),
      ["pre_validation_original.mp4", "pre_validation_overlay.json", "108_Ada.pdf"],
    );
    expect(plan.wantPdf).toBe(true);
    const missingPdf = evaluateRecallPieces(plan, {
      cacheByPhase: {
        pre: { overlay, originalVideoBlob: original, kinematicsSnapshot: { csv_filename: "a.csv" } },
      },
      pdfOk: false,
    });
    expect(missingPdf.complete).toBe(false);
    expect(missingPdf.missing).toContain("Clinic PDF");
  });

  test("empty boot recall does not consume the 45s cooldown", () => {
    const empty = summarizeRecallRows([]);
    expect(empty.attempted).toBe(false);
    expect(shouldReuseRecentRecall(empty, Date.now() - 1000, Date.now())).toBe(false);
    const real = summarizeRecallRows([{ expected: true, complete: true }]);
    expect(real.attempted).toBe(true);
    expect(shouldReuseRecentRecall(real, Date.now() - 1000, Date.now())).toBe(true);
    expect(shouldReuseRecentRecall(real, Date.now() - 1000, Date.now(), { force: true })).toBe(false);
    expect(shouldReuseRecentRecall(real, Date.now() - 46000, Date.now())).toBe(false);
  });

  test("home screen waits for restored patients instead of recalling an empty list", () => {
    expect(shouldWaitForPatientsBeforeRecall([], { standalone: true, waitedMs: 0 })).toBe(true);
    expect(shouldWaitForPatientsBeforeRecall([], { standalone: true, waitedMs: 30000 })).toBe(false);
    expect(shouldWaitForPatientsBeforeRecall([patient()], { standalone: true, waitedMs: 0 })).toBe(false);
    expect(shouldWaitForPatientsBeforeRecall([], { standalone: false, waitedMs: 0 })).toBe(false);
  });

  test("home screen recalls one patient at a time", () => {
    expect(recallPoolSize({ standalone: true })).toBe(1);
    expect(recallPoolSize({ standalone: false })).toBe(2);
  });
});
